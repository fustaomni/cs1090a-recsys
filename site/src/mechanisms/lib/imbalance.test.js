import { describe, expect, it } from "vitest";
import data from "../../data/movielens.json";
import { errors, shares, weightedLine } from "./macro.js";
import { mulberry32, normal } from "./random.js";

// Technique 3's fitted model: 6000 ratings drawn from a class mix (seed 11), one noisy
// signal (seed 12), a line fitted with or without 1 / n_k weights.
const REAL = shares(data.splits["0.8/0.9"].training.counts);
const UNIFORM = [0.2, 0.2, 0.2, 0.2, 0.2];

function sample(mix, n, seed) {
  const rng = mulberry32(seed);
  return Array.from({ length: n }, () => {
    const u = rng();
    let level = 0;
    let running = mix[0];
    while (u > running && level < 4) running += mix[(level += 1)];
    return level + 1;
  });
}

function fitted(mix, balanced) {
  const actual = sample(mix, 6000, 11);
  const rng = mulberry32(12);
  const signal = actual.map((y) => y + 1.2 * normal(rng));
  const line = weightedLine(signal, actual, balanced);
  return errors(signal.map(line), actual);
}

describe("class weights, as Technique 3 shows them", () => {
  it("lower macro error and raise pooled error with the real shares", () => {
    const plain = fitted(REAL, false);
    const weighted = fitted(REAL, true);
    expect(weighted.macroRmse).toBeLessThan(plain.macroRmse);
    expect(weighted.pooledRmse).toBeGreaterThan(plain.pooledRmse);
  });

  it("change almost nothing at a uniform mix, where the weights are nearly equal", () => {
    const plain = fitted(UNIFORM, false);
    const weighted = fitted(UNIFORM, true);
    expect(Math.abs(weighted.macroRmse - plain.macroRmse)).toBeLessThan(0.02);
    expect(Math.abs(weighted.pooledRmse - plain.pooledRmse)).toBeLessThan(0.02);
  });
});
