import { describe, expect, it } from "vitest";
import { ensemblePredict, forest } from "./ensemble.js";
import { forestRatings } from "./ratings.js";

// Model 8's data: the first 200 of forestRatings({ seed: 101, n: 240 }), and its query rows.
const FEATURES = ["user", "movie", "genre", "noise"];
const rows = forestRatings({ seed: 101, n: 240 }).slice(0, 200);
const queries = forestRatings({ seed: 9, n: 20 });

describe("bagging, as Model 8 shows it", () => {
  it("keeps one bootstrap tree's expected prediction, so averaging lowers variance, not bias", () => {
    let single = 0;
    let averaged = 0;
    let count = 0;
    for (let seed = 1; seed <= 40; seed += 1) {
      const members = forest(rows, FEATURES, { trees: 20, minLeaf: 3, seed });
      for (const query of queries) {
        single += members[0].model.predict(query);
        averaged += ensemblePredict(members, query, 20);
        count += 1;
      }
    }
    expect(count).toBe(800);
    expect(Math.abs(single / count - averaged / count)).toBeLessThan(0.1);
  });
});
