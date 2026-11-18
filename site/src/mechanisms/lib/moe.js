// The mixture of experts behind Model 15 and Techniques 13 to 15, as scripts/moe.py computes
// it: a max-subtracted softmax gate and its weighted mix, gate features read strictly before
// the request, the four training-history buckets, and per-bucket RMSE with a percentile
// bootstrap that resamples users, the unit the ratings cluster by (Technique 9).

import { percentile, schemeWeights, weightedRmse } from "./inference.js";
import { mulberry32 } from "./random.js";

export function softmax(scores) {
  const top = Math.max(...scores);
  const raised = scores.map((score) => Math.exp(score - top));
  const total = raised.reduce((sum, value) => sum + value, 0);
  return raised.map((value) => value / total);
}

export function mix(predictions, weights) {
  if (predictions.length !== weights.length) {
    throw new Error("each expert's prediction needs exactly one gate weight");
  }
  return predictions.reduce((sum, prediction, i) => sum + prediction * weights[i], 0);
}

export function usable(rows, boundary) {
  return {
    before: rows.filter((row) => row.time < boundary),
    blocked: rows.filter((row) => row.time >= boundary),
  };
}

export function gateFeatures(training, target, boundary) {
  if (training.some((row) => row.time >= boundary)) {
    throw new Error("leakage: a training rating is at or after the boundary");
  }
  return {
    userCount: training.filter((row) => row.user === target.user).length,
    movieCount: training.filter((row) => row.movie === target.movie).length,
  };
}

export function bucketOf({ userCount, movieCount }) {
  if (userCount > 0 && movieCount > 0) return "warm";
  if (movieCount > 0) return "new user";
  if (userCount > 0) return "new movie";
  return "both new";
}

export function pooledRmse(rows) {
  const total = rows.reduce((sum, row) => sum + (row.prediction - row.rating) ** 2, 0);
  return Math.sqrt(total / rows.length);
}

function interval(rows, draws, seed) {
  const ids = [...new Set(rows.map((row) => row.user))];
  const index = new Map(ids.map((id, i) => [id, i]));
  const local = rows.map((row) => ({ ...row, user: index.get(row.user) }));
  const rng = mulberry32(seed);
  const values = Array.from({ length: draws }, () =>
    weightedRmse(local, "prediction", schemeWeights(local, "user", ids.length, 0, rng)),
  );
  return { low: percentile(values, 0.025), high: percentile(values, 0.975) };
}

export function bucketReport(rows, { minimum = 30, draws = 200, seed = 1 } = {}) {
  const groups = new Map();
  rows.forEach((row) => groups.set(row.bucket, [...(groups.get(row.bucket) ?? []), row]));
  const report = {};
  groups.forEach((group, bucket) => {
    report[bucket] = {
      n: group.length,
      rmse: pooledRmse(group),
      small: group.length < minimum,
      ...interval(group, draws, seed),
    };
  });
  return report;
}
