import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./RaMicroSachstandsCard.jsx", () => ({ default: () => null }));
vi.mock("../components/StaDialog.jsx", () => ({ default: () => null }));
vi.mock("../components/AbschlussberichtDialog.jsx", () => ({ default: () => null }));
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
