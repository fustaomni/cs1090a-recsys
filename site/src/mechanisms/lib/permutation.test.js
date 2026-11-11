import { describe, expect, it } from "vitest";
import { outsideSupport, permuted } from "./importance.js";
import { mulberry32 } from "./random.js";
import { forestRatings } from "./ratings.js";

// Technique 8's data at its default rho: the first 220 rows train, the last 80 are shuffled.
const rows = forestRatings({ seed: 121, n: 300, rho: 0.6 });
const train = rows.slice(0, 220);
const later = rows.slice(220);

// The page's support radius: the 95th percentile of each training point's nearest neighbour.
function supportRadius(points) {
  const nearest = points.map((row, i) => {
    let best = Infinity;
    points.forEach((other, k) => {
      if (k === i) return;
      best = Math.min(best, Math.hypot(row.user - other.user, row.movie - other.movie));
    });
    return best;
  });
  return nearest.sort((a, b) => a - b)[Math.floor(0.95 * nearest.length)];
}

describe("permutation importance, as Technique 8 shows it", () => {
  it("sends more shuffled points outside the training data plainly than conditionally", () => {
    const radius = supportRadius(train);
    const keys = ["user", "movie"];
    const plain = outsideSupport(train, permuted(later, "user", mulberry32(5)), keys, radius);
    const kept = outsideSupport(train, permuted(later, "user", mulberry32(5), "movie"), keys, radius);
    expect(plain).toBeGreaterThan(kept);
  });
});
