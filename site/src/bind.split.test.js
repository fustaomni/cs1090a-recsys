// site/src/bind.split.test.js
// A.350: Milestone 2's cut quantiles on the site are the recorded windows' shares of the ratings.
import { describe, expect, it } from "vitest";
import results from "./data/results.json";
import { bind, sources } from "./bind.js";

function ratings(window) {
  const section = results.milestones.find((entry) => entry.milestone === "M2");
  const pointer = `/split_audit/windows/${window}/ratings`;
  return section.entries.find((entry) => entry.pointer === pointer).value;
}

describe("Milestone 2's cut quantiles", () => {
  it("are the recorded shares of every rating before each cut, to two places", () => {
    const [train, validation, test] = ["train", "validation", "test"].map(ratings);
    const total = train + validation + test;
    const values = sources();
    expect(values.ms2ValidationQuantile).toBeCloseTo(train / total, 2);
    expect(values.ms2TestQuantile).toBeCloseTo((train + validation) / total, 2);
    expect(values.ms2ValidationQuantile).toBeLessThan(values.ms2TestQuantile);
  });

  it("render through bind, never typed", () => {
    expect(bind("{ms2ValidationQuantile} and {ms2TestQuantile}")).toMatch(/^0\.\d+ and 0\.\d+$/);
  });
});
