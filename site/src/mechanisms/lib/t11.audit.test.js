import { describe, expect, it } from "vitest";
import { audit, conformalHalfWidth, coverageData } from "./coverage.js";

// Technique 11's audited readouts on its own 30 test ratings, computed as T11.jsx does.
const { calibration, test } = coverageData({ seed: 151 });
const at = (level) => audit(test, conformalHalfWidth(calibration, level), level);

describe("the coverage audit, as Technique 11 shows it", () => {
  it("covers both groups in full at 95% on the page's 30 test ratings", () => {
    const result = at(0.95);
    expect(result.coverage).toBe(1);
    for (const group of result.groups) expect(group.coverage).toBe(1);
  });

  it("lets the noisier light raters fall short of the heavy ones at 80%", () => {
    const [light, heavy] = at(0.8).groups;
    expect(light.coverage).toBeLessThan(heavy.coverage);
  });

  it("finds the default gap within two binomial standard errors on 30 ratings", () => {
    const result = at(0.95);
    const se = Math.sqrt((0.95 * 0.05) / result.rows.length);
    expect(Math.abs(result.coverage - 0.95)).toBeLessThanOrEqual(2 * se);
  });
});
