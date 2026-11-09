// site/src/bind.test.js
import { describe, expect, it } from "vitest";
import { bind, sources } from "./bind.js";

describe("bind (A.245)", () => {
  it("formats a bound figure from its source", () => {
    expect(bind("{ratings} ratings", { ratings: 1234567 })).toBe("1,234,567 ratings");
  });

  it("refuses an unbound token", () => {
    expect(() => bind("{nothing} here", {})).toThrow(/unbound \{nothing\}/);
  });

  it("reads every count from the site data", () => {
    const values = sources();
    for (const name of ["ratings", "users", "moviesRated", "models", "techniques", "milestones"]) {
      expect(values[name]).toBeGreaterThan(0);
    }
  });

  it("renders a model or technique by its number and its name (A.258)", () => {
    expect(bind("{model:10}")).toBe("Model 10 · AdaBoost for regression");
    expect(bind("{technique:4}")).toBe("Technique 4 · PCA");
  });

  it("refuses a model or technique the data does not hold (A.258)", () => {
    expect(() => bind("{model:15}")).toThrow(/unbound \{model:15\}/);
  });
});
