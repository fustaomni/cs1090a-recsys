import { describe, expect, it } from "vitest";
import data from "../../data/movielens.json";
import { LOCKED, riskRegister } from "./register.js";

describe("the risk register, as Technique 1 shows it", () => {
  it("shows no rating value until the split is made, for either pair of cutoffs", () => {
    for (const key of Object.keys(data.splits)) {
      const locked = riskRegister(data, key, false);
      expect(locked[1][1]).toBe(LOCKED);
      expect(locked.map((row) => row[1]).join(" ")).not.toMatch(/skew|★/);
      expect(riskRegister(data, key, true)[1][1]).toMatch(/skew/);
    }
  });

  it("counts the movies with fewer than 8 training ratings from the bins 1, 2-3 and 4-7", () => {
    const tail = data.splits["0.8/0.9"].training.movieTail;
    expect(tail.slice(0, 3).map((b) => b.to)).toEqual([1, 3, 7]);
    expect(tail[3].from).toBe(8);
    const sparse = tail.slice(0, 3).reduce((t, b) => t + b.count, 0);
    const evidence = riskRegister(data, "0.8/0.9", true)[2][1];
    expect(evidence.startsWith(`${sparse.toLocaleString("en-US")} of `)).toBe(true);
  });
});
