// site/src/mechanisms/lib/crossed.js
// Model 13, the crossed random-effects bias model (A.246): a rating is the grand mean plus a
// user offset plus a movie offset, each partially pooled toward zero. Each offset is its
// summed residual over n + sigma^2 / tau^2, so a user or movie with few ratings is pulled
// toward the crowd and one with many keeps its own; the two are fitted by alternating updates.
import { mulberry32, normal } from "./random.js";
import { toLevel } from "./ratings.js";

export const CROSSED = { users: 10, movies: 10, mean: 3.4, userSpread: 0.6, movieSpread: 0.7, noise: 0.8 };
const NAMED = 0.3;

export function crossedRatings({ seed = 131 } = {}) {
  const rng = mulberry32(seed);
  const userOffsets = Array.from({ length: CROSSED.users }, () => CROSSED.userSpread * normal(rng));
  const movieOffsets = Array.from({ length: CROSSED.movies }, () => CROSSED.movieSpread * normal(rng));
  const rows = [];
  for (let user = 0; user < CROSSED.users; user += 1) {
    // Users differ in how much they rate: the first rate a few movies, the last nearly all.
    const share = 0.15 + (0.8 * user) / (CROSSED.users - 1);
    for (let movie = 0; movie < CROSSED.movies; movie += 1) {
      if (rng() < share) {
        const latent =
          CROSSED.mean + userOffsets[user] + movieOffsets[movie] + CROSSED.noise * normal(rng);
        rows.push({ user, movie, rating: toLevel(latent) });
      }
    }
  }
  return { rows, userOffsets, movieOffsets };
}

function counts(rows, key, size) {
  const total = new Array(size).fill(0);
  for (const row of rows) {
    total[row[key]] += 1;
  }
  return total;
}

function update(rows, key, offsets, residual, count, pooling) {
  const sums = new Array(offsets.length).fill(0);
  for (const row of rows) {
    sums[row[key]] += residual(row);
  }
  for (let index = 0; index < offsets.length; index += 1) {
    const denominator = count[index] + pooling;
    offsets[index] = denominator > 0 ? sums[index] / denominator : 0;
  }
}

export function crossedFit(rows, { pooling = 1, iterations = 60 } = {}) {
  const mu = rows.reduce((total, row) => total + row.rating, 0) / rows.length;
  const users = new Array(CROSSED.users).fill(0);
  const movies = new Array(CROSSED.movies).fill(0);
  const userCount = counts(rows, "user", CROSSED.users);
  const movieCount = counts(rows, "movie", CROSSED.movies);
  for (let step = 0; step < iterations; step += 1) {
    update(rows, "user", users, (row) => row.rating - mu - movies[row.movie], userCount, pooling);
    update(rows, "movie", movies, (row) => row.rating - mu - users[row.user], movieCount, pooling);
  }
  return { mu, users, movies, userCount, movieCount };
}

export function predict(fit, user, movie) {
  return fit.mu + fit.users[user] + fit.movies[movie];
}

export function kept(count, pooling) {
  return count + pooling > 0 ? count / (count + pooling) : 0;
}

export function userLabel(offset) {
  if (offset <= -NAMED) return "harsh critic";
  if (offset >= NAMED) return "generous rater";
  return "typical rater";
}

export function movieLabel(offset) {
  if (offset <= -NAMED) return "panned";
  if (offset >= NAMED) return "acclaimed";
  return "middling";
}
