import { describe, it, expect } from "vitest";
import { firmaSpeicherKey } from "./parteiLogik.js";

describe("firmaSpeicherKey", () => {
  it("firma-first, versicherung wird ignoriert", () => {
    expect(firmaSpeicherKey({ firma: "ADAC Autoversicherung AG", name: "X", versicherung: "HUK" }))
      .toBe("ADAC Autoversicherung AG");
  });

  it("name-Fallback, nicht versicherung", () => {
    expect(firmaSpeicherKey({ name: "Baloise AG", versicherung: "HUK" }))
      .toBe("Baloise AG");
  });

  it("leerer/None-Input liefert leeren String", () => {
    expect(firmaSpeicherKey(null)).toBe("");
    expect(firmaSpeicherKey(undefined)).toBe("");
    expect(firmaSpeicherKey({})).toBe("");
  });
});
