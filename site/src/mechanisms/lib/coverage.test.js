// site/src/mechanisms/lib/coverage.test.js
import { describe, expect, it } from "vitest";
import { audit, conformalHalfWidth, coverageData, intervalScore } from "./coverage.js";

describe("prediction-interval coverage audit (A.246)", () => {
  it("scores an interval by its width, plus 2/alpha times any miss", () => {
    expect(intervalScore(2, 4, 3, 0.1)).toBe(2);
    expect(intervalScore(2, 4, 5, 0.1)).toBeCloseTo(2 + 20 * 1, 10);
    expect(intervalScore(2, 4, 1, 0.1)).toBeCloseTo(2 + 20 * 1, 10);
  });

  it("widens the interval as the nominal level rises", () => {
    const { calibration } = coverageData();
    expect(conformalHalfWidth(calibration, 0.8)).toBeLessThanOrEqual(conformalHalfWidth(calibration, 0.95));
  });

  it("covers close to its nominal level overall, as split conformal guarantees marginally", () => {
    const { calibration, test } = coverageData({ seed: 151, test: 4000 });
    const result = audit(test, conformalHalfWidth(calibration, 0.9), 0.9);
    expect(result.coverage).toBeGreaterThan(0.86);
  });

  it("covers the noisier light raters less than the heavy raters with one width for all", () => {
    const { calibration, test } = coverageData({ seed: 151, test: 4000 });
    const result = audit(test, conformalHalfWidth(calibration, 0.9), 0.9);
    const [light, heavy] = result.groups;
    expect(light.coverage).toBeLessThan(heavy.coverage);
  });
});
