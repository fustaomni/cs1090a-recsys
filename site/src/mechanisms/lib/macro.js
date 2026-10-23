// Pooled against macro-averaged error on the five rating levels. Pooled error weights each
// level by how common it is; macro error averages the five per-level errors equally, so for
// a constant prediction it does not depend on the class mix at all. RMSE^M is declared as
// the root of the macro-averaged MSE.

const LEVELS = [1, 2, 3, 4, 5];

export function shares(counts) {
  const total = counts.reduce((s, n) => s + n, 0);
  return counts.map((n) => n / total);
}

// Errors of a constant prediction c, computed exactly from the level shares.
export function constantErrors(c, weights) {
  const squared = LEVELS.map((k) => (k - c) ** 2);
  const absolute = LEVELS.map((k) => Math.abs(k - c));
  const pooledMse = squared.reduce((s, e, i) => s + weights[i] * e, 0);
  return {
    pooledRmse: Math.sqrt(pooledMse),
    pooledMae: absolute.reduce((s, e, i) => s + weights[i] * e, 0),
    macroRmse: Math.sqrt(squared.reduce((s, e) => s + e, 0) / 5),
    macroMae: absolute.reduce((s, e) => s + e, 0) / 5,
    perLevel: absolute,
  };
}

// The same four metrics for any predictions against observed levels.
export function errors(predictions, actual) {
  const byLevel = LEVELS.map((k) => {
    const mine = actual.map((y, i) => [y, predictions[i]]).filter(([y]) => y === k);
    const mse = mine.reduce((s, [y, p]) => s + (p - y) ** 2, 0) / mine.length;
    const mae = mine.reduce((s, [y, p]) => s + Math.abs(p - y), 0) / mine.length;
    return { mse, mae, count: mine.length };
  });
  const n = actual.length;
  return {
    pooledRmse: Math.sqrt(predictions.reduce((s, p, i) => s + (p - actual[i]) ** 2, 0) / n),
    pooledMae: predictions.reduce((s, p, i) => s + Math.abs(p - actual[i]), 0) / n,
    macroRmse: Math.sqrt(byLevel.reduce((s, l) => s + l.mse, 0) / 5),
    macroMae: byLevel.reduce((s, l) => s + l.mae, 0) / 5,
    perLevel: byLevel.map((l) => Math.sqrt(l.mse)),
  };
}

// Weighted least squares of the rating on one signal; weights 1 / n_k make every level count
// equally in training, an optional intervention distinct from the evaluation metric.
export function weightedLine(signal, actual, balanced) {
  const counts = LEVELS.map((k) => actual.filter((y) => y === k).length);
  const w = actual.map((y) => (balanced ? 1 / counts[y - 1] : 1));
  const total = w.reduce((s, v) => s + v, 0);
  const mx = signal.reduce((s, x, i) => s + w[i] * x, 0) / total;
  const my = actual.reduce((s, y, i) => s + w[i] * y, 0) / total;
  let sxy = 0;
  let sxx = 0;
  signal.forEach((x, i) => {
    sxy += w[i] * (x - mx) * (actual[i] - my);
    sxx += w[i] * (x - mx) ** 2;
  });
  const slope = sxy / sxx;
  return (x) => my + slope * (x - mx);
}
