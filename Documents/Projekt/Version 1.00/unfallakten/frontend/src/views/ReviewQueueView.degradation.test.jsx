import { describe, it, expect } from "vitest";
import { istDegradiert } from "./ReviewQueueView.jsx";

describe("istDegradiert", () => {
  it("true bei llm_degradiert === 1", () => {
    expect(istDegradiert({ llm_degradiert: 1 })).toBe(true);
  });
  it("false bei 0/null/undefined", () => {
    expect(istDegradiert({ llm_degradiert: 0 })).toBe(false);
    expect(istDegradiert({ llm_degradiert: null })).toBe(false);
    expect(istDegradiert({})).toBe(false);
    expect(istDegradiert(null)).toBe(false);
  });
});
