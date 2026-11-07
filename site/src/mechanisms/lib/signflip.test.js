// site/src/mechanisms/lib/signflip.test.js
import { describe, expect, it } from "vitest";
import { blockData, exactNull, exactP, pFloor, rowLevelP, statistic, userMeans } from "./signflip.js";

describe("user-level sign-flip permutation test (A.246)", () => {
  const blocks = blockData({ seed: 171, users: 5 });
  const means = userMeans(blocks);

  it("keeps the observed statistic with no flips and negates it with all flipped", () => {
    const observed = statistic(means, means.map(() => 1));
    expect(statistic(means, means.map(() => -1))).toBeCloseTo(-observed, 12);
  });

  it("enumerates every sign pattern, symmetric about zero", () => {
    const values = exactNull(means);
    expect(values).toHaveLength(2 ** means.length);
    expect(values.reduce((total, value) => total + value, 0)).toBeCloseTo(0, 10);
  });

  it("cannot go below 2 / 2^n, so five users can never reach 0.05", () => {
    expect(exactP(means)).toBeGreaterThanOrEqual(pFloor(5) - 1e-12);
    expect(pFloor(5)).toBeGreaterThan(0.05);
    expect(pFloor(6)).toBeLessThan(0.05);
  });

  it("is less certain than a row-level flip that ignores the clustering by user", () => {
    expect(rowLevelP(blocks)).toBeLessThan(exactP(means));
  });
});
