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

const REFERENZWERKSTATT = {
  name: "Möser Arno - Karosseriefachbetrieb",
  adresse: "Philipp-Reis-Straße 9",
  plz_ort: "63128 Dietzenbach",
  telefon: "06074-25936",
  km_genannt: 16.0,
  quelle: "vhv_block",
};

describe("FelderEditor Objekt-Felder (referenzwerkstatt editierbar)", () => {
  it("rendert Objekt-Felder als editierbare Zeilen statt JSON-Box", () => {
    render(<FelderEditor
      felder={{ referenzwerkstatt: REFERENZWERKSTATT }}
      onChange={() => {}} />);
    expect(screen.getByDisplayValue("Möser Arno - Karosseriefachbetrieb")).toBeTruthy();
    expect(screen.getByDisplayValue("63128 Dietzenbach")).toBeTruthy();
    expect(screen.queryByText(/"name"/)).toBeNull();
  });

  it("meldet Textänderungen mit unveränderten übrigen Schlüsseln", () => {
    const onChange = vi.fn();
    render(<FelderEditor
      felder={{ referenzwerkstatt: REFERENZWERKSTATT }}
      onChange={onChange} />);
    const input = screen.getByDisplayValue("Philipp-Reis-Straße 9");
    fireEvent.change(input, { target: { value: "Hauptstraße 1" } });
    const [key, neu] = onChange.mock.calls.at(-1);
    expect(key).toBe("referenzwerkstatt");
    expect(neu.adresse).toBe("Hauptstraße 1");
    expect(neu.name).toBe("Möser Arno - Karosseriefachbetrieb");
    expect(neu.km_genannt).toBe(16.0);
  });

  it("parst km_genannt nach Blur als Zahl (deutsches Format)", () => {
    const onChange = vi.fn();
    render(<Harness initial={{ referenzwerkstatt: REFERENZWERKSTATT }} onChange={onChange} />);
    const input = screen.getByDisplayValue("16");
    fireEvent.change(input, { target: { value: "18,5" } });
    fireEvent.blur(input);
    const [key, neu] = onChange.mock.calls.at(-1);
    expect(key).toBe("referenzwerkstatt");
    expect(neu.km_genannt).toBe(18.5);
  });

  it("maschinelle Prüfwerte bleiben schreibgeschützt", () => {
    render(<FelderEditor
      felder={{ referenzwerkstatt: {
        ...REFERENZWERKSTATT,
        km_echt: 21.3, bewertung: "unzumutbar",
        geprueft_am: "2026-08-07", geprueft_gegen_akte: "1280/25",
      } }}
      onChange={() => {}} />);
    expect(screen.getByText("21,3")).toBeTruthy();
    expect(screen.getByText("unzumutbar")).toBeTruthy();
    expect(screen.queryByDisplayValue("21,3")).toBeNull();
    expect(screen.queryByDisplayValue("unzumutbar")).toBeNull();
    expect(screen.queryByDisplayValue("vhv_block")).toBeNull();
  });

  it("verschachtelte Unterobjekte bleiben JSON-Anzeige", () => {
    render(<FelderEditor
      felder={{ referenzwerkstatt: {
        ...REFERENZWERKSTATT,
        stundensaetze: { karosserie: 98.5 },
      } }}
      onChange={() => {}} />);
    expect(screen.getByText(/"karosserie"/)).toBeTruthy();
    expect(screen.getByDisplayValue("Möser Arno - Karosseriefachbetrieb")).toBeTruthy();
  });

  it("nicht-flache Arrays bleiben JSON-Anzeige", () => {
    render(<FelderEditor
      felder={{ verschachtelt: [{ kind: { tief: 1 } }] }}
      onChange={() => {}} />);
    expect(screen.getByText(/"tief"/)).toBeTruthy();
  });
});
