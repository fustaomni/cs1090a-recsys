import { mulberry32, normal } from "./random.js";

// Synthetic ratings shaped like MovieLens: standardised user and movie history, possibly
// correlated, and a rating on the five integer levels a user can submit. The true effects
// are known, so a lab can show what a fit recovers and what it absorbs.

export const TRUTH = { intercept: 3.6, user: 0.5, movie: 0.5, noise: 0.8 };

export function toLevel(value) {
  return Math.min(5, Math.max(1, Math.round(value)));
}

export function ratings({ seed = 7, n = 300, rho = 0, levels = true } = {}) {
  const rng = mulberry32(seed);
  const spread = Math.sqrt(1 - rho * rho);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const movie = rho * user + spread * normal(rng);
    const latent =
      TRUTH.intercept + TRUTH.user * user + TRUTH.movie * movie + TRUTH.noise * normal(rng);
    rows.push({ user, movie, rating: levels ? toLevel(latent) : latent });
  }
  return rows;
}

// Ratings that depend on a user's mean and on how many movies they have rated, with genuine
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
    const movie = rho * user + spread * normal(rng);
    const noise = normal(rng);
    const latent =
      TRUTH.intercept + TRUTH.user * user + TRUTH.movie * movie + TRUTH.noise * normal(rng);
    rows.push({ user, movie, noise, rating: toLevel(latent) });
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
    const movie = normal(rng);
    const recency = normal(rng);
    const group = Math.floor(rng() * 3);
    const latent =
      TRUTH.intercept +
      0.5 * user +
      0.4 * movie -
      0.3 * user * movie +
      0.2 * (group === 2 ? 1 : 0) +
      0.7 * normal(rng);
    rows.push({ user, movie, recency, group, rating: toLevel(latent) });
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

// Ratings for a tree: prior-only user and movie means (continuous), a binary genre that
// matters, and an ordinal age band, with a threshold effect a tree captures in one split.
export function treeRatings({ seed = 91, n = 360 } = {}) {
  const rng = mulberry32(seed);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = 3.6 + 0.55 * normal(rng);
    const movie = 3.5 + 0.5 * normal(rng);
    const genre = rng() < 0.3 ? 1 : 0;
    const age = Math.floor(rng() * 7);
    const latent =
      3.6 +
      0.7 * (user - 3.6) +
      0.6 * (movie - 3.5) +
      0.45 * genre +
      (age >= 5 ? 0.3 : 0) +
      (user > 4 && movie > 3.8 ? 0.4 : 0) +
      0.75 * normal(rng);
    rows.push({ user, movie, genre, age, rating: toLevel(latent) });
  }
  return rows;
}

// Ratings for ensembles: correlated user and movie histories, a binary genre that matters, a
// continuous column of pure noise, and a corner where both histories are high. Rows are in
// time order.
export function forestRatings({ seed = 101, n = 240, rho = 0.6 } = {}) {
  const rng = mulberry32(seed);
  const spread = Math.sqrt(1 - rho * rho);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const user = normal(rng);
    const movie = rho * user + spread * normal(rng);
    const genre = rng() < 0.3 ? 1 : 0;
    const noise = normal(rng);
    const latent =
      3.6 +
      0.55 * user +
      0.45 * movie +
      0.4 * genre +
      (user > 0.5 && movie > 0.3 ? 0.45 : 0) +
      0.8 * normal(rng);
    rows.push({ user, movie, genre, noise, rating: toLevel(latent) });
  }
  return rows;
}

// Ratings that drift over time: later ratings run higher and lean less on user history, so a
// model fitted on the past meets a slightly different world. Rows are in time order.
export function driftRatings({ seed = 111, n = 300 } = {}) {
  const rng = mulberry32(seed);
  const spread = Math.sqrt(1 - 0.6 * 0.6);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const t = index / n;
    const user = normal(rng);
    const movie = 0.6 * user + spread * normal(rng);
    const genre = rng() < 0.3 ? 1 : 0;
    const noise = normal(rng);
    const latent =
      3.2 +
      1.2 * t +
      (0.8 - 0.7 * t) * user +
      0.45 * movie +
      0.4 * genre +
      0.7 * normal(rng);
    rows.push({ user, movie, genre, noise, rating: toLevel(latent) });
  }
  return rows;
}

// Out-of-fold predictions from two base models for stacking: both track the same underlying
// rating, the second with a small bias, and their errors share a controllable correlation.
// Rows are in time order.
export function stackingRatings({ seed = 161, n = 500, correlation = 0.6 } = {}) {
  const rng = mulberry32(seed);
  const own = Math.sqrt(1 - correlation * correlation);
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const mean = 3.6 + 0.6 * normal(rng);
    const rating = toLevel(mean + 0.7 * normal(rng));
    const first = normal(rng);
    const second = correlation * first + own * normal(rng);
    const user = Math.floor(rng() * 40);
    rows.push({ user, rating, base: [mean + 0.45 * first, mean + 0.15 + 0.55 * second] });
  }
  return rows;
}

// Time-stamped ratings with MovieLens-like front-loading: most users arrive early and rate
// many movies within days, so equal calendar slices would hold very unequal row counts.
// Timestamps are whole days, so ties occur, and ratings drift upward slowly over time.
export function timedRatings({ seed = 181, users = 160, movies = 120 } = {}) {
  const rng = mulberry32(seed);
  const movieEffect = Array.from({ length: movies }, () => 0.45 * normal(rng));
  const rows = [];
  for (let user = 0; user < users; user += 1) {
    const effect = 0.5 * normal(rng);
    const start = Math.floor(1000 * rng() ** 3);
    const count = 6 + Math.floor(30 * rng() ** 2);
    for (let k = 0; k < count; k += 1) {
      const time = Math.min(999, start + Math.floor(-25 * Math.log(1 - rng())));
      const movie = Math.floor(rng() ** 1.5 * movies);
      const drift = 0.3 * (time / 1000);
      const latent = 3.5 + effect + movieEffect[movie] + drift + 0.7 * normal(rng);
      rows.push({ user, movie, time, rating: toLevel(latent) });
    }
  }
  return rows;
}

// A known true rating surface over two histories, for the bias-variance lab: smooth, with a
// ridge and a corner, so complexity helps up to a point. Ratings are the truth plus noise,
// rounded to five levels; rows are in time order.
export function trueSurface(row) {
  const ridge = 0.35 * row.movie * Math.exp(-0.3 * row.movie ** 2);
  const corner = row.user > 0.6 && row.movie > 0.4 ? 0.5 : 0;
  return 3.5 + 0.55 * Math.tanh(1.2 * row.user) + ridge + corner;
}

export function surfaceRatings({ seed = 191, n = 300, noise = 0.7 } = {}) {
  const rng = mulberry32(seed);
  return Array.from({ length: n }, () => {
    const row = { user: 1.6 * normal(rng), movie: 1.6 * normal(rng) };
    return { ...row, rating: toLevel(trueSurface(row) + noise * normal(rng)) };
  });
}
