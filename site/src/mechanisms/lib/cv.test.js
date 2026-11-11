import { describe, expect, it } from "vitest";
import { randomFolds } from "./importance.js";
import { mulberry32 } from "./random.js";
import { timedRatings } from "./ratings.js";
import { blockEdges, byTime, cutAt, rollingFolds } from "./timecv.js";

// Technique 5's data: timedRatings({ seed: 181 }) in time order, folds before the 0.8 cut.
const rows = byTime(timedRatings({ seed: 181 }));
const tval = cutAt(rows, 0.8);

describe("cross-validation, as Technique 5 shows it", () => {
  it("trains every random fold on more rows than the first rolling fold, for every k", () => {
    for (let blocks = 3; blocks <= 8; blocks += 1) {
      const rolling = rollingFolds(blockEdges(rows, tval, blocks));
      const random = randomFolds(tval, blocks, mulberry32(7));
      const fewestRandom = Math.min(...random.map((held) => tval - held.length));
      expect(rolling[0].train.length).toBeLessThan(fewestRandom);
    }
  });
});
