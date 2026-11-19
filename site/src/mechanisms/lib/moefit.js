// site/src/mechanisms/lib/moefit.js
// A.359: the mixture of experts on one train, validate and test time split. Users and movies
// arrive over time, so a later window holds every cold-start bucket. The gate is fitted on the
// validation window by gradient descent on the mixture's squared error, with the experts held
// fixed: the router is fitted apart from the experts, as EM splits the problem.

import { softmax } from "./moe.js";
import { mulberry32, normal } from "./random.js";
import { toLevel } from "./ratings.js";

// Ratings from users and movies that arrive over the whole horizon. A user rates only movies
// already released, half the time one released within the last FRESH days, so new movies
// collect ratings soon after they appear. Structure and noise draw from separate streams.
const FRESH = 100;

export function arrivingRatings({ seed = 191, users = 220, movies = 160, horizon = 1000 } = {}) {
  const rng = mulberry32(seed);
  const noise = mulberry32(seed + 7919);
  const release = Array.from({ length: movies }, () => Math.floor(horizon * rng()));
  const movieEffect = release.map(() => 0.45 * normal(noise));
  const rows = [];
  for (let user = 0; user < users; user += 1) {
    const start = Math.floor(horizon * rng());
    const effect = 0.5 * normal(noise);
    const count = 6 + Math.floor(30 * rng());
    for (let k = 0; k < count; k += 1) {
      const time = Math.min(horizon - 1, start + Math.floor(-120 * Math.log(1 - rng())));
      const out = release.flatMap((day, movie) => (day <= time ? [movie] : []));
      const fresh = out.filter((movie) => time - release[movie] < FRESH);
      const pool = fresh.length > 0 && rng() < 0.5 ? fresh : out;
      if (pool.length === 0) continue;
      const movie = pool[Math.floor(rng() * pool.length)];
      const latent =
        3.5 + effect + movieEffect[movie] + 0.3 * (time / horizon) + 0.7 * normal(noise);
      rows.push({ user, movie, time, rating: toLevel(latent) });
    }
  }
  return rows.sort((p, q) => p.time - q.time || p.user - q.user || p.movie - q.movie);
}

export function threeWindows(rows, { validateFrom, testFrom }) {
  if (!(validateFrom < testFrom)) {
    throw new Error("the validation window must end before the test window starts");
  }
  return {
    train: rows.filter((row) => row.time < validateFrom),
    validate: rows.filter((row) => row.time >= validateFrom && row.time < testFrom),
    test: rows.filter((row) => row.time >= testFrom),
  };
}

// Each row's user and movie counts in the history, which must end before the earliest row.
export function windowFeatures(history, rows) {
  if (rows.length === 0) return [];
  const boundary = Math.min(...rows.map((row) => row.time));
  if (history.some((row) => row.time >= boundary)) {
    throw new Error("leakage: a history rating is at or after the window it describes");
  }
  const tally = (key) => {
    const counts = new Map();
    history.forEach((row) => counts.set(row[key], (counts.get(row[key]) ?? 0) + 1));
    return counts;
  };
  const users = tally("user");
  const movies = tally("movie");
  return rows.map((row) => ({
    userCount: users.get(row.user) ?? 0,
    movieCount: movies.get(row.movie) ?? 0,
  }));
}

export function softmaxT(scores, temperature = 1) {
  if (!(temperature > 0)) throw new Error("the temperature must be positive");
  return softmax(scores.map((score) => score / temperature));
}

export function topK(weights, k) {
  const kept = new Set(
    weights
      .map((weight, index) => [weight, index])
      .sort((p, q) => q[0] - p[0] || p[1] - q[1])
      .slice(0, k)
      .map(([, index]) => index),
  );
  const total = weights.reduce((sum, weight, index) => sum + (kept.has(index) ? weight : 0), 0);
  return weights.map((weight, index) => (kept.has(index) ? weight / total : 0));
}

// The gate reads an intercept and the two counts as log(1 + n), one linear score per expert.
const inputs = ({ userCount, movieCount }) => [1, Math.log1p(userCount), Math.log1p(movieCount)];

export function gateWeights(theta, feature, temperature = 1) {
  const x = inputs(feature);
  const scores = theta.map((row) => row.reduce((sum, value, i) => sum + value * x[i], 0));
  return softmaxT(scores, temperature);
}

const mixOne = (weights, prediction) =>
  weights.reduce((sum, weight, j) => sum + weight * prediction[j], 0);

export function mixturePredict(theta, features, predictions) {
  return features.map((feature, i) => mixOne(gateWeights(theta, feature), predictions[i]));
}

// Gradient descent on the mean squared error of the mixture, from the uniform gate (zeros).
// d loss / d score_j = 2 (mix - y) w_j (p_j - mix), times each input for its weight.
export function fitGate({ features, predictions, targets, rate = 0.5, steps = 400 }) {
  const experts = predictions[0].length;
  const theta = Array.from({ length: experts }, () => [0, 0, 0]);
  const xs = features.map(inputs);
  const losses = [];
  for (let step = 0; step <= steps; step += 1) {
    const gradient = theta.map(() => [0, 0, 0]);
    let loss = 0;
    features.forEach((feature, i) => {
      const weights = gateWeights(theta, feature);
      const mix = mixOne(weights, predictions[i]);
      const error = mix - targets[i];
      loss += error * error;
      weights.forEach((weight, j) => {
        const slope = 2 * error * weight * (predictions[i][j] - mix);
        xs[i].forEach((value, d) => {
          gradient[j][d] += slope * value;
        });
      });
    });
    losses.push(loss / features.length);
    if (step === steps) break;
    theta.forEach((row, j) =>
      row.forEach((_, d) => {
        row[d] -= (rate * gradient[j][d]) / features.length;
      }),
    );
  }
  return { theta, losses };
}

export function utilisation(weightRows) {
  return weightRows[0].map(
    (_, j) => weightRows.reduce((sum, row) => sum + row[j], 0) / weightRows.length,
  );
}
