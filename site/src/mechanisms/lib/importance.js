// Variable importance for a fitted model on held-out rows: how much error rises when a feature
// is shuffled (plainly, or only within strata of a correlated feature), or when the model is
// refitted without it.

export function shuffled(values, rng) {
  const copy = values.slice();
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rng() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

// The rank of each row's `given` value, cut into equal-count bins.
export function strata(rows, given, bins) {
  const order = rows.map((_, i) => i).sort((a, b) => rows[a][given] - rows[b][given]);
  const bin = new Array(rows.length);
  order.forEach((row, rank) => {
    bin[row] = Math.min(bins - 1, Math.floor((rank * bins) / rows.length));
  });
  return bin;
}

// Plain permutation shuffles a feature across all rows; conditional permutation shuffles it
// only among rows in the same stratum of a correlated feature, keeping combinations realistic.
export function permuted(rows, feature, rng, given = null, bins = 5) {
  const values = rows.map((row) => row[feature]);
  if (!given) {
    const mixed = shuffled(values, rng);
    return rows.map((row, i) => ({ ...row, [feature]: mixed[i] }));
  }
  const bin = strata(rows, given, bins);
  const result = rows.map((row) => ({ ...row }));
  for (let b = 0; b < bins; b += 1) {
    const members = rows.map((_, i) => i).filter((i) => bin[i] === b);
    const mixed = shuffled(
      members.map((i) => values[i]),
      rng,
    );
    members.forEach((i, k) => {
      result[i][feature] = mixed[k];
    });
  }
  return result;
}

export function rmseOf(predict, rows) {
  return Math.sqrt(rows.reduce((s, row) => s + (predict(row) - row.rating) ** 2, 0) / rows.length);
}

// The rise in RMSE over several shuffles, returned per repeat so its spread can be shown.
export function permutationRises(predict, rows, feature, rng, repeats, given = null) {
  const base = rmseOf(predict, rows);
  return Array.from(
    { length: repeats },
    () => rmseOf(predict, permuted(rows, feature, rng, given)) - base,
  );
}

// Shares of the total, with negative rises counted as zero.
export function shares(values) {
  const positive = values.map((v) => Math.max(v, 0));
  const total = positive.reduce((s, v) => s + v, 0) || 1;
  return positive.map((v) => v / total);
}

// A point is outside the training support when its nearest training point is farther than
// the given radius, in the two named features.
export function outsideSupport(trainRows, rows, keys, radius) {
  const outside = rows.filter((row) => {
    let best = Infinity;
    for (const point of trainRows) {
      const d = Math.hypot(...keys.map((key) => row[key] - point[key]));
      if (d < best) best = d;
    }
    return best > radius;
  });
  return outside.length / rows.length;
}

// Random k-fold indices, for the cross-validation that ignores time.
export function randomFolds(n, k, rng) {
  const order = shuffled(
    Array.from({ length: n }, (_, i) => i),
    rng,
  );
  return Array.from({ length: k }, (_, fold) => order.filter((_, i) => i % k === fold));
}
