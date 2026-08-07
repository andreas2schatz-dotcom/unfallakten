import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {},
  apiAktenanlage: {},
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

import { useState } from "react";
import { FelderEditor } from "./ReviewQueueView.jsx";

const POSITIONEN = [
  { bezeichnung: "Sachverständigengebühren", betrag: 1316.62 },
  { bezeichnung: "Kostenpauschale", betrag: 30.0 },
];

// Wie im DetailPanel: onChange landet im dirty-State und re-rendert den
// Editor mit dem aktualisierten Wert.
function Harness({ initial, onChange }) {
  const [felder, setFelder] = useState(initial);
  return (
    <FelderEditor
      felder={felder}
      onChange={(k, v) => {
        onChange(k, v);
        setFelder(f => ({ ...f, [k]: v }));
      }}
    />
  );
}

describe("FelderEditor Positions-Tabelle (Befund 1280/25)", () => {
  it("rendert positionen als editierbare Tabelle statt JSON-Box", () => {
    render(<FelderEditor felder={{ positionen: POSITIONEN }} onChange={() => {}} />);
    expect(screen.getByDisplayValue("Sachverständigengebühren")).toBeTruthy();
    expect(screen.getByDisplayValue("1316,62")).toBeTruthy();
    expect(screen.queryByText(/"betrag"/)).toBeNull();
  });

  it("meldet Betragsänderungen nach Blur als Zahl (deutsches Format)", () => {
    const onChange = vi.fn();
    render(<Harness initial={{ positionen: POSITIONEN }} onChange={onChange} />);
    const input = screen.getByDisplayValue("1316,62");
    fireEvent.change(input, { target: { value: "5.448,62" } });
    fireEvent.blur(input);
    const [key, neu] = onChange.mock.calls.at(-1);
    expect(key).toBe("positionen");
    expect(neu[0].betrag).toBe(5448.62);
    expect(neu[0].bezeichnung).toBe("Sachverständigengebühren");
    expect(neu[1]).toEqual({ bezeichnung: "Kostenpauschale", betrag: 30.0 });
  });

  it("meldet Textänderungen an der Bezeichnung", () => {
    const onChange = vi.fn();
    render(<Harness initial={{ positionen: POSITIONEN }} onChange={onChange} />);
    const input = screen.getByDisplayValue("Kostenpauschale");
    fireEvent.change(input, { target: { value: "Unkostenpauschale" } });
    const [key, neu] = onChange.mock.calls.at(-1);
    expect(key).toBe("positionen");
    expect(neu[1].bezeichnung).toBe("Unkostenpauschale");
  });

  it("kann eine Zeile hinzufügen", () => {
    const onChange = vi.fn();
    render(<FelderEditor felder={{ positionen: POSITIONEN }} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /Zeile hinzufügen/ }));
    const [key, neu] = onChange.mock.calls.at(-1);
    expect(key).toBe("positionen");
    expect(neu.length).toBe(3);
  });

  it("kann eine Zeile entfernen", () => {
    const onChange = vi.fn();
    render(<FelderEditor felder={{ positionen: POSITIONEN }} onChange={onChange} />);
    fireEvent.click(screen.getAllByRole("button", { name: /Zeile entfernen/ })[0]);
    const [key, neu] = onChange.mock.calls.at(-1);
    expect(key).toBe("positionen");
    expect(neu).toEqual([{ bezeichnung: "Kostenpauschale", betrag: 30.0 }]);
  });

  it("zahlungen werden ebenfalls als Tabelle editierbar", () => {
    render(<FelderEditor
      felder={{ zahlungen: [{ betrag: 7751.54, art: "Zahlung per Überweisung" }] }}
      onChange={() => {}} />);
    expect(screen.getByDisplayValue("7751,54")).toBeTruthy();
    expect(screen.getByDisplayValue("Zahlung per Überweisung")).toBeTruthy();
  });

  it("einzelne Objekte (referenzwerkstatt) bleiben JSON-Anzeige", () => {
    render(<FelderEditor
      felder={{ referenzwerkstatt: { name: "Möser Arno", km_genannt: 16.0 } }}
      onChange={() => {}} />);
    expect(screen.queryByDisplayValue("Möser Arno")).toBeNull();
    expect(screen.getByText(/"name"/)).toBeTruthy();
  });

  it("skalare Felder bleiben einfache Eingabefelder", () => {
    const onChange = vi.fn();
    render(<FelderEditor felder={{ versicherer: "VHV" }} onChange={onChange} />);
    const input = screen.getByDisplayValue("VHV");
    fireEvent.change(input, { target: { value: "VHV Allgemeine" } });
    expect(onChange).toHaveBeenCalledWith("versicherer", "VHV Allgemeine");
  });
});
