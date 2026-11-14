import { describe, expect, it } from "vitest";
import { correlation, encodings, smoothed } from "./encoding.js";
import { timedRatings } from "./ratings.js";
import { byTime, cutAt } from "./timecv.js";

describe("the smoothed encoding, as Technique 2 shows it", () => {
  it("becomes the global mean with no history at every prior weight, m = 0 included", () => {
    for (const m of [0, 1, 10, 50]) expect(smoothed(0, 4.6, m, 3.591)).toBe(3.591);
    const coded = encodings([{ user: 1, rating: 5 }, { user: 1, rating: 1 }], 0, 3.6);
    expect(coded[0].prior).toBe(3.6);
    expect(coded[1].prior).toBe(5);
  });

  it("splits the in-sample excess into the own-rating leak and the further drop to later rows", () => {
    const rows = byTime(timedRatings({ seed: 181 }));
    const cut = cutAt(rows, 0.8);
    const train = rows.slice(0, cut);
    const later = rows.slice(cut);
    const mean = train.reduce((s, r) => s + r.rating, 0) / train.length;
    const coded = encodings(train, 10, mean);
    const ys = train.map((r) => r.rating);
    const naiveIn = correlation(coded.map((c) => c.naive), ys);
    const priorIn = correlation(coded.map((c) => c.prior), ys);
    const totals = new Map();
    for (const r of train) {
      const t = totals.get(r.user) ?? { sum: 0, n: 0 };
      totals.set(r.user, { sum: t.sum + r.rating, n: t.n + 1 });
    }
    const forLater = later.map((r) => {
      const t = totals.get(r.user) ?? { sum: 0, n: 0 };
      return smoothed(t.n, t.n ? t.sum / t.n : mean, 10, mean);
    });
    const outside = correlation(forLater, later.map((r) => r.rating));
    expect(naiveIn).toBeGreaterThan(priorIn);
    expect(priorIn).toBeGreaterThan(outside);
  });
});
