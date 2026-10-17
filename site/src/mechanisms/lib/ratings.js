import { mulberry32, normal } from "./random.js";

// Synthetic ratings shaped like MovieLens: standardised user and film history, possibly
// correlated, and a rating on the five integer levels a user can submit. The true effects
// are known, so a lab can show what a fit recovers and what it absorbs.

export const TRUTH = { intercept: 3.6, user: 0.5, film: 0.5, noise: 0.8 };

export function toLevel(value) {
  return Math.min(5, Math.max(1, Math.round(value)));
}

export function ratings({ seed = 7, n = 300, rho = 0, levels = true } = {}) {
  const rng = mulberry32(seed);
  const spread = Math.sqrt(1 - rho * rho);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const film = rho * user + spread * normal(rng);
    const latent =
      TRUTH.intercept + TRUTH.user * user + TRUTH.film * film + TRUTH.noise * normal(rng);
    rows.push({ user, film, rating: levels ? toLevel(latent) : latent });
  }
  return rows;
}

// Ratings that depend on a user's mean and on how many films they have rated, with genuine
// curvature in the count and an interaction between the two. Count is in hundreds of ratings
// and always positive, so uncentred count and count squared are nearly collinear.
export const CURVED = { intercept: 3.6, user: 0.45, count: 0.3, square: -0.1, both: 0.15 };

export function historyRatings({ seed = 21, n = 400 } = {}) {
  const rng = mulberry32(seed);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const count = Math.exp(0.6 * normal(rng));
    const shift = count - 1;
    const latent =
      CURVED.intercept +
      CURVED.user * user +
      CURVED.count * shift +
      CURVED.square * shift * shift +
      CURVED.both * user * shift +
      0.75 * normal(rng);
    rows.push({ user, count, rating: toLevel(latent) });
  }
  return rows;
}

// Ratings with two correlated predictors that matter and one that does not, so a selection
// method can be judged on what it keeps and what it drops. Rows are in time order.
export function selectionRatings({ seed = 41, n = 160, rho = 0.8 } = {}) {
  const rng = mulberry32(seed);
  const spread = Math.sqrt(1 - rho * rho);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const film = rho * user + spread * normal(rng);
    const noise = normal(rng);
    const latent =
      TRUTH.intercept + TRUTH.user * user + TRUTH.film * film + TRUTH.noise * normal(rng);
    rows.push({ user, film, noise, rating: toLevel(latent) });
  }
  return rows;
}

// Ratings from three standardised histories and one categorical demographic, with a curved
// interaction a neighbourhood method can pick up and a linear one cannot. Rows are in time
// order.
export function neighbourRatings({ seed = 71, n = 300 } = {}) {
  const rng = mulberry32(seed);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const film = normal(rng);
    const recency = normal(rng);
    const group = Math.floor(rng() * 3);
    const latent =
      TRUTH.intercept +
      0.5 * user +
      0.4 * film -
      0.3 * user * film +
      0.2 * (group === 2 ? 1 : 0) +
      0.7 * normal(rng);
    rows.push({ user, film, recency, group, rating: toLevel(latent) });
  }
  return rows;
}

// A wide table for PCA: six histories driven by one factor, four by another, a count in large
// units driven by a third, and, when planted, a signal hidden in the small difference between
// two near-duplicate columns, a direction PCA ranks last.
export const WIDE_NAMES = [
  "drama share",
  "drama mean",
  "crime share",
  "thriller share",
  "war share",
  "film-noir share",
  "comedy share",
  "comedy mean",
  "children's share",
  "animation share",
  "rating count",
];

export function wideRatings({ seed = 81, n = 300, planted = false } = {}) {
  const rng = mulberry32(seed);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const first = normal(rng);
    const second = normal(rng);
    const third = normal(rng);
    const own = Array.from({ length: 10 }, () => normal(rng));
    const features = [
      ...own.slice(0, 6).map((e) => first + 0.25 * e),
      ...own.slice(6).map((e) => second + 0.4 * e),
      20 * third,
    ];
    const hidden = planted ? (0.9 * (own[0] - own[1])) / Math.SQRT2 : 0;
    const latent =
      TRUTH.intercept + 0.5 * first + 0.35 * second + 0.15 * third + hidden + 0.7 * normal(rng);
    rows.push({ features, rating: toLevel(latent) });
  }
  return rows;
}
