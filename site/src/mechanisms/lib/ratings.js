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
