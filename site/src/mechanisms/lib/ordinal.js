// site/src/mechanisms/lib/ordinal.js
// Model 14, ordinal regression as a cumulative link model (A.246): a hidden score
// eta = b1 * user + b2 * movie, cut into the five star levels by four ordered cut-points,
// with P(Y <= j) = logistic(theta_j - eta). Fitted by maximum likelihood with analytic
// gradients; the cut-points are free, so their spacing is learned rather than assumed equal.
import { mulberry32, normal } from "./random.js";

export const ORDINAL = { n: 50, user: 1.1, movie: 0.8, cuts: [-2.4, -1.1, 0.4, 1.9] };
const LEVELS = 5;

function logisticDraw(rng) {
  const u = Math.min(1 - 1e-12, Math.max(1e-12, rng()));
  return Math.log(u / (1 - u));
}

export function bucket(score, cuts, shift = 0) {
  let level = 1;
  for (const cut of cuts) {
    if (score >= cut + shift) level += 1;
  }
  return level;
}

export function ordinalRatings({ seed = 141, n = ORDINAL.n } = {}) {
  const rng = mulberry32(seed);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const movie = normal(rng);
    const latent = ORDINAL.user * user + ORDINAL.movie * movie + logisticDraw(rng);
    rows.push({ user, movie, rating: bucket(latent, ORDINAL.cuts) });
  }
  return rows;
}

const sigmoid = (value) => 1 / (1 + Math.exp(-value));

function bounds(cuts, rating) {
  const lower = rating === 1 ? -Infinity : cuts[rating - 2];
  const upper = rating === LEVELS ? Infinity : cuts[rating - 1];
  return [lower, upper];
}

export function score(params, row) {
  return params.b1 * row.user + params.b2 * row.movie;
}

export function logLikelihood(rows, params) {
  let total = 0;
  for (const row of rows) {
    const eta = score(params, row);
    const [lower, upper] = bounds(params.cuts, row.rating);
    const probability = sigmoid(upper - eta) - sigmoid(lower - eta);
    total += Math.log(Math.max(probability, 1e-300));
  }
  return total;
}

export function start() {
  return { b1: 0, b2: 0, cuts: [-1.5, -0.5, 0.5, 1.5] };
}

export function clmFit(rows, { iterations = 3000, rate = 0.1 } = {}) {
  let params = start();
  for (let step = 0; step < iterations; step += 1) {
    const grad = { b1: 0, b2: 0, cuts: [0, 0, 0, 0] };
    for (const row of rows) {
      const eta = score(params, row);
      const [lower, upper] = bounds(params.cuts, row.rating);
      const fu = Number.isFinite(upper) ? sigmoid(upper - eta) : 1;
      const fl = Number.isFinite(lower) ? sigmoid(lower - eta) : 0;
      const du = Number.isFinite(upper) ? fu * (1 - fu) : 0;
      const dl = Number.isFinite(lower) ? fl * (1 - fl) : 0;
      const probability = Math.max(fu - fl, 1e-12);
      const deta = -(du - dl) / probability;
      grad.b1 += deta * row.user;
      grad.b2 += deta * row.movie;
      if (row.rating < LEVELS) grad.cuts[row.rating - 1] += du / probability;
      if (row.rating > 1) grad.cuts[row.rating - 2] -= dl / probability;
    }
    const scale = rate / rows.length;
    const cuts = params.cuts.map((cut, index) => cut + scale * grad.cuts[index]);
    for (let index = 1; index < cuts.length; index += 1) {
      cuts[index] = Math.max(cuts[index], cuts[index - 1] + 1e-3);
    }
    params = { b1: params.b1 + scale * grad.b1, b2: params.b2 + scale * grad.b2, cuts };
  }
  return params;
}
