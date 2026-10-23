import { mean } from "./stats.js";

// Tuning by time-ordered folds: rows are in time order, cut into equal blocks, and fold k
// trains on blocks 1..k and validates on block k + 1, so validation is always later.

export function logGrid(high, low, count) {
  const ratio = Math.log(low / high) / (count - 1);
  return Array.from({ length: count }, (_, index) => high * Math.exp(ratio * index));
}

export function rollingFolds(n, blocks) {
  const edges = Array.from({ length: blocks + 1 }, (_, index) => Math.round((n * index) / blocks));
  const span = (from, to) => Array.from({ length: to - from }, (_, index) => from + index);
  return Array.from({ length: blocks - 1 }, (_, k) => ({
    train: span(0, edges[k + 1]),
    valid: span(edges[k + 1], edges[k + 2]),
  }));
}

// Mean validation error and its standard error across folds, at each lambda.
export function curve(lambdas, folds, score) {
  return lambdas.map((lambda) => {
    const errors = folds.map((fold) => score(fold, lambda));
    const centre = mean(errors);
    const squares = errors.reduce((total, e) => total + (e - centre) ** 2, 0);
    const spread = Math.sqrt(squares / (errors.length - 1));
    return { lambda, error: centre, se: spread / Math.sqrt(errors.length) };
  });
}

// The minimum, and the simplest setting whose error is within one standard error of it. By
// default the simplest is the largest penalty; a caller can say what simpler means instead.
const largerPenalty = (a, b) => a.lambda > b.lambda;

export function oneStandardError(points, simpler = largerPenalty) {
  const best = points.reduce((low, point) => (point.error < low.error ? point : low));
  const ceiling = best.error + best.se;
  const simplest = points
    .filter((point) => point.error <= ceiling)
    .reduce((top, point) => (simpler(point, top) ? point : top));
  return { best, simplest };
}
