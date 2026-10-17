// Resampling for crossed data, where every rating belongs to one user and one film. A scheme
// turns one bootstrap draw into a weight per rating:
//   row          ratings drawn with replacement (treats ratings as independent)
//   user         users drawn with replacement, each bringing all of their ratings
//   pigeonhole   users and films drawn independently (Owen 2007); a rating's weight is the
//                product of its user's and its film's counts
// Any statistic computed with those weights gives one bootstrap replicate.

import { mulberry32, normal } from "./random.js";

function counts(size, rng) {
  const result = new Array(size).fill(0);
  for (let i = 0; i < size; i += 1) result[Math.floor(rng() * size)] += 1;
  return result;
}

export function schemeWeights(rows, scheme, users, films, rng) {
  if (scheme === "row") return counts(rows.length, rng);
  const userCounts = counts(users, rng);
  if (scheme === "user") return rows.map((row) => userCounts[row.user]);
  const filmCounts = counts(films, rng);
  return rows.map((row) => userCounts[row.user] * filmCounts[row.film]);
}

export function weightedRmse(rows, key, weights) {
  let total = 0;
  let mass = 0;
  rows.forEach((row, i) => {
    total += weights[i] * (row[key] - row.rating) ** 2;
    mass += weights[i];
  });
  return Math.sqrt(total / mass);
}

export function percentile(values, q) {
  const sorted = values.slice().sort((a, b) => a - b);
  const position = q * (sorted.length - 1);
  const low = Math.floor(position);
  const high = Math.ceil(position);
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

// For each replicate: model A's RMSE, model B's RMSE and their paired difference, all computed
// on the same resampled weights.
export function replicates(rows, scheme, users, films, draws, seed) {
  const rng = mulberry32(seed);
  return Array.from({ length: draws }, () => {
    const weights = schemeWeights(rows, scheme, users, films, rng);
    const a = weightedRmse(rows, "a", weights);
    const b = weightedRmse(rows, "b", weights);
    return { a, b, difference: a - b };
  });
}

// Test ratings for two models on crossed, unbalanced data: user and film effects make errors
// correlated within users and within films, the two models share part of their error, and
// the second model's error is three quarters the size of the first's.
export function crossedRatings(options = {}) {
  const { seed = 151, users = 60, films = 40, userEffect = 0.35 } = options;
  const { filmEffect = 0.25, shared = 0.7, gap = 0.03 } = options;
  const rng = mulberry32(seed);
  const userShift = Array.from({ length: users }, () => userEffect * normal(rng));
  const filmShift = Array.from({ length: films }, () => filmEffect * normal(rng));
  const userErrA = Array.from({ length: users }, () => 0.3 * normal(rng));
  const own = Math.sqrt(1 - shared ** 2);
  const userErrB = userErrA.map((e) => shared * e + own * 0.3 * normal(rng));
  const filmErr = Array.from({ length: films }, () => 0.2 * normal(rng));
  const rows = [];
  for (let user = 0; user < users; user += 1) {
    const many = Math.max(3, Math.round(Math.exp(2.6 + 0.8 * normal(rng))));
    for (let k = 0; k < many; k += 1) {
      const film = Math.floor(rng() ** 1.6 * films);
      const mean = 3.6 + userShift[user] + filmShift[film];
      const rating = Math.min(5, Math.max(1, Math.round(mean + 0.8 * normal(rng))));
      const common = filmErr[film] + 0.4 * normal(rng);
      const a = mean + userErrA[user] + common + gap * Math.sign(normal(rng));
      const b = mean + 0.75 * (userErrB[user] + shared * common + 0.4 * own * normal(rng));
      rows.push({ user, film, rating, a, b });
    }
  }
  return { rows, users, films };
}
