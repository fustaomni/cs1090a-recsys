// Bagging and random forests built from the CART trees in tree.js. Each tree is grown deep on
// a bootstrap sample of the rows; a random forest also restricts every split to a random
// subset of mtry features. The ensemble predicts the mean of its trees.

import { mulberry32 } from "./random.js";
import { grow, view } from "./tree.js";

export function forest(rows, features, options = {}) {
  const { trees = 40, mtry = features.length, minLeaf = 3, sampleFraction = 1 } = options;
  const { seed = 1 } = options;
  const rng = mulberry32(seed);
  const n = rows.length;
  const size = Math.max(2, Math.round(n * sampleFraction));
  return Array.from({ length: trees }, () => {
    const picked = Array.from({ length: size }, () => Math.floor(rng() * n));
    const tree = grow(
      picked.map((i) => rows[i]),
      features,
      { minLeaf, mtry, rng },
    );
    return { tree, model: view(tree), inBag: new Set(picked) };
  });
}

export function ensemblePredict(members, row, count = members.length) {
  let total = 0;
  for (let b = 0; b < count; b += 1) total += members[b].model.predict(row);
  return total / count;
}

// Out-of-bag: each training row is predicted only by the trees whose sample left it out.
export function outOfBag(members, rows, count = members.length) {
  return rows.map((row, i) => {
    let total = 0;
    let used = 0;
    for (let b = 0; b < count; b += 1) {
      if (members[b].inBag.has(i)) continue;
      total += members[b].model.predict(row);
      used += 1;
    }
    return used > 0 ? total / used : NaN;
  });
}

// The variance of an average of B correlated trees, Var = rho sigma^2 + (1 - rho) sigma^2 / B,
// estimated across independent datasets: sigma^2 from single trees, rho from the average.
export function varianceAcrossDatasets(makeRows, features, queries, options = {}) {
  const { datasets = 6, trees = 30, ...rest } = options;
  const predictions = Array.from({ length: datasets }, (_, d) => {
    const members = forest(makeRows(1000 + d), features, { trees, seed: 2000 + d, ...rest });
    return queries.map((query) => {
      let running = 0;
      return members.map((member, b) => {
        running += member.model.predict(query);
        return running / (b + 1);
      });
    });
  });
  const varianceAt = (b) => {
    let total = 0;
    queries.forEach((_, q) => {
      const values = predictions.map((perDataset) => perDataset[q][b]);
      const centre = values.reduce((s, v) => s + v, 0) / values.length;
      total += values.reduce((s, v) => s + (v - centre) ** 2, 0) / (values.length - 1);
    });
    return total / queries.length;
  };
  const perB = Array.from({ length: trees }, (_, b) => varianceAt(b));
  const sigma2 = (() => {
    let total = 0;
    queries.forEach((_, q) => {
      const values = predictions.map((perDataset) => perDataset[q][0]);
      const centre = values.reduce((s, v) => s + v, 0) / values.length;
      total += values.reduce((s, v) => s + (v - centre) ** 2, 0) / (values.length - 1);
    });
    return total / queries.length;
  })();
  const last = perB[trees - 1];
  const rho = Math.min(1, Math.max(0, (last - sigma2 / trees) / (sigma2 * (1 - 1 / trees))));
  return { perB, sigma2, rho, floor: rho * sigma2 };
}

// How often each feature is split on at each depth, across the trees.
export function splitFrequency(members, features, depths = 3) {
  return Array.from({ length: depths }, (_, depth) => {
    const counts = Object.fromEntries(features.map((f) => [f, 0]));
    let total = 0;
    for (const member of members) {
      for (const node of member.model.internal) {
        if (node.depth !== depth) continue;
        counts[node.feature] += 1;
        total += 1;
      }
    }
    return features.map((f) => (total > 0 ? counts[f] / total : 0));
  });
}

// A piecewise-constant surface sampled on a fine grid and drawn with every cell edge doubled,
// so cells stay flat and meet in vertical walls: an average of step functions is still one.
export function blockSurface(predict, xKey, yKey, [x0, x1], [y0, y1], count, fixed) {
  const edges = (low, high) =>
    Array.from({ length: count + 1 }, (_, i) => low + ((high - low) * i) / count);
  const xs = edges(x0, x1);
  const ys = edges(y0, y1);
  const doubled = (list) => list.slice(0, -1).flatMap((v, i) => [v, list[i + 1]]);
  const centre = (list, index) => {
    const cell = Math.floor(index / 2);
    return (list[cell] + list[cell + 1]) / 2;
  };
  const x = doubled(xs);
  const y = doubled(ys);
  const cache = new Map();
  const z = y.map((_, r) =>
    x.map((__, c) => {
      const key = `${Math.floor(r / 2)},${Math.floor(c / 2)}`;
      if (!cache.has(key)) {
        cache.set(key, predict({ ...fixed, [xKey]: centre(xs, c), [yKey]: centre(ys, r) }));
      }
      return cache.get(key);
    }),
  );
  return { x, y, z };
}
