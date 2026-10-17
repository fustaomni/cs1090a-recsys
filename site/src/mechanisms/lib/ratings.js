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
