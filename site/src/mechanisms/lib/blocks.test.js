import { describe, expect, it } from "vitest";
import { blockData, exactP, rowLevelP, userMeans } from "./signflip.js";

// Technique 12's data: blockData({ seed: 171, users }) at every user count its slider allows.
describe("the sign-flip test, as Technique 12 shows it", () => {
  it("is less certain than the row-level flip for every user count from 5 to 12", () => {
    for (let users = 5; users <= 12; users += 1) {
      const blocks = blockData({ seed: 171, users });
      expect(rowLevelP(blocks)).toBeLessThan(exactP(userMeans(blocks)));
    }
  });
});
