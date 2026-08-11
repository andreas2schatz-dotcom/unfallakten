import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./RaMicroSachstandsCard.jsx", () => ({ default: () => null }));
vi.mock("../components/StaDialog.jsx", () => ({
  default: ({ az }) => <div data-testid="sta-dialog">{az}</div>,
}));
vi.mock("../components/AbschlussberichtDialog.jsx", () => ({
  default: ({ az }) => <div data-testid="abschluss-dialog">{az}</div>,
}));
vi.mock("../api.js", () => ({
  beteiligte: { liste: vi.fn(() => Promise.resolve({ beteiligte: [] })) },
  word: {
    generieren: vi.fn(() => Promise.resolve({})),
    vorschau: vi.fn(() => Promise.resolve({})),
  },
}));

import { word as apiWord } from "../api.js";
import WordSection from "./WordSection.jsx";

const AKTE = { id: "1/26", az: "1/26", hq: 100 };
const GHPV = { id: 7, rolle: "gegner", versicherung: "HUK Coburg", kuerzel: "GHPV" };

beforeEach(() => {
  vi.clearAllMocks();
});

describe("M-1 – Dialoge erhalten die Basis-AZ (nicht die volle RA-MICRO-AZ)", () => {
  const AKTE_VOLL = { id: "312/26", az: "312/26 AS", az_roh: "312/26", hq: 100 };

  it("StaDialog bekommt az_roh, auch wenn akte.az das SB-Kürzel trägt", () => {
    render(<WordSection akte={AKTE_VOLL} st={{}} dispatch={vi.fn()} />);
    fireEvent.click(screen.getByText(/Sachstandsanfrage erstellen/));
    expect(screen.getByTestId("sta-dialog").textContent).toBe("312/26");
  });

  it("AbschlussberichtDialog bekommt ebenfalls az_roh", () => {
    render(<WordSection akte={AKTE_VOLL} st={{}} dispatch={vi.fn()} />);
    fireEvent.click(screen.getByText(/Bericht kuratieren/));
    expect(screen.getByTestId("abschluss-dialog").textContent).toBe("312/26");
  });
});

describe("I-2 – Adressat-Vorbelegung WordSection", () => {
  it("sendet die GHPV-id auch wenn Beteiligte erst nach dem Mount ankommen", async () => {
    const { rerender } = render(
      <WordSection akte={AKTE} st={{}} dispatch={vi.fn()} />
    );
    rerender(
      <WordSection akte={AKTE} st={{ beteiligte: [GHPV] }} dispatch={vi.fn()} />
    );

    fireEvent.click(screen.getAllByText(/Generieren & Herunterladen/)[0]);
    await waitFor(() => expect(apiWord.generieren).toHaveBeenCalled());
    expect(apiWord.generieren.mock.calls[0][2]).toBe(7);
  });
});
