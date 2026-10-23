import { describe, expect, it } from "vitest";
import { randomFolds } from "./importance.js";
import { mulberry32 } from "./random.js";
import { timedRatings } from "./ratings.js";
import { baseline, blockEdges, byTime, cutAt, futureLeaks, rollingFolds } from "./timecv.js";

const rows = byTime(timedRatings());
const tval = cutAt(rows, 0.8);
const edges = blockEdges(rows, tval, 5);

describe("time-ordered folds", () => {
  it("front-loads the ratings: over 40% arrive in the first fifth of the time span", () => {
    const early = rows.filter((r) => r.time < 200).length;
    expect(early / rows.length).toBeGreaterThan(0.4);
  });

  it("cuts the training window at a timestamp boundary", () => {
    expect(rows[tval - 1].time).toBeLessThan(rows[tval].time);
  });

  it("makes blocks of nearly equal row count that never split a timestamp", () => {
    const sizes = edges.slice(1).map((e, i) => e - edges[i]);
    expect(Math.max(...sizes) - Math.min(...sizes)).toBeLessThan(0.2 * (tval / 5));
    for (const e of edges.slice(1, -1)) expect(rows[e - 1].time).toBeLessThan(rows[e].time);
  });

  it("validates every rolling fold strictly after its training rows, before T_val", () => {
    for (const fold of rollingFolds(edges, { gap: 10 })) {
      const lastTrain = Math.max(...fold.train.map((i) => rows[i].time));
      const firstValid = Math.min(...fold.valid.map((i) => rows[i].time));
      expect(lastTrain).toBeLessThan(firstValid);
      expect(Math.max(...fold.valid)).toBeLessThan(tval);
      expect(fold.gap).toHaveLength(10);
    }
  });

  it("keeps only the latest blocks in a sliding window", () => {
    const folds = rollingFolds(edges, { sliding: true, width: 2 });
    expect(folds[3].train[0]).toBe(edges[2]);
  });
});

describe("leaks", () => {
  it("finds no future leaks in rolling folds and many in random folds", () => {
    const window = rows.slice(0, tval);
    for (const fold of rollingFolds(edges)) {
      const leaks = futureLeaks(
        fold.train.map((i) => rows[i]),
        fold.valid.map((i) => rows[i]),
      );
      expect(leaks).toBe(0);
    }
    const folds = randomFolds(window.length, 5, mulberry32(3));
    const held = new Set(folds[0]);
    const leaks = futureLeaks(
      window.filter((_, i) => !held.has(i)),
      folds[0].map((i) => window[i]),
    );
    expect(leaks).toBeGreaterThan(folds[0].length / 4);
  });

  it("fits a shrunk user-and-movie baseline that beats the mean on later rows", () => {
    const predict = baseline(rows.slice(0, tval));
    const later = rows.slice(tval);
    const mu = rows.slice(0, tval).reduce((s, r) => s + r.rating, 0) / tval;
    const rmse = (f) =>
      Math.sqrt(later.reduce((s, r) => s + (f(r) - r.rating) ** 2, 0) / later.length);
    expect(rmse(predict)).toBeLessThan(rmse(() => mu));
  });
});
