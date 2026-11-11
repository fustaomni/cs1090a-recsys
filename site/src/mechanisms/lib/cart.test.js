import { describe, expect, it } from "vitest";
import { treeRatings } from "./ratings.js";
import { splitCurve } from "./tree.js";

// Model 7's training rows: the first 300 of treeRatings({ seed: 91, n: 360 }).
const rows = treeRatings({ seed: 91, n: 360 }).slice(0, 300);
const ys = rows.map((row) => row.rating);
const distinct = (feature) => new Set(rows.map((row) => row[feature])).size;

describe("the split search, as Model 7 shows it", () => {
  it("offers one threshold per gap between distinct values: one for genre, nearly one per row for a mean", () => {
    const genre = splitCurve(rows, ys, "genre", 5);
    const user = splitCurve(rows, ys, "user", 5);
    expect(distinct("genre")).toBe(2);
    expect(genre).toHaveLength(1);
    expect(user.length).toBeLessThanOrEqual(distinct("user") - 1);
    expect(user.length).toBeGreaterThan(rows.length / 2);
  });
});
