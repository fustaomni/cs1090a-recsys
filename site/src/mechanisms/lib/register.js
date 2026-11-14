// site/src/mechanisms/lib/register.js
// Technique 1's risk register, generated from the MovieLens summary. Every row shows counts
// except the one on the rating target, which shows rating values, so it stays locked until the
// split is made, exactly as Phase 1B does.
import { fixed } from "./format.js";

export const LOCKED = "Locked until the split is made: press the button above";
const integer = (n) => n.toLocaleString("en-US");
const percent = (part, whole) => `${fixed((100 * part) / whole, 1)}%`;

export function riskRegister(data, key, split) {
  const summary = data.splits[key];
  const training = summary.training;
  const windows = summary.windows;
  const s = data.structure;
  const cut = data.quantiles[key.split("/")[0]];
  const span = data.timeline.cumulative.length - 1;
  // Doubling bins end inclusively at 1, 3 and 7, so these are the movies with fewer than 8.
  const sparse = training.movieTail.filter((b) => b.to < 8).reduce((t, b) => t + b.count, 0);
  const smallestGenre = training.genres.reduce((a, g) => (g.ratings < a.ratings ? g : a));
  return [
    [
      "Ratings are front-loaded in time",
      `${percent(cut.index, s.ratings)} of all ratings were submitted by ${cut.date}, ` +
        `day ${cut.day} of ${span}`,
      "Cut at quantiles of time, never at calendar dates; blocks of equal row count for folds",
      "Phase 2",
    ],
    [
      "The ordinal target is imbalanced",
      split
        ? `${percent(training.counts[0], windows.train.rows)} of training ratings are 1★ ` +
          `against ${percent(training.counts[3], windows.train.rows)} at 4★; ` +
          `skew ${fixed(training.skew, 2)}`
        : LOCKED,
      "Report macro-averaged error beside pooled error, with the constant floors",
      "Phase 0",
    ],
    [
      "Long tails and cold start",
      `${integer(sparse)} of ${integer(windows.train.movies)} movies have fewer than 8 ` +
        `training ratings; ${integer(summary.testUsersUnseen)} of ` +
        `${integer(summary.testUsers)} test users never appear in training`,
      "Smoothed prior-only encodings, a count feature, and cold-start thresholds",
      "Phases 3 and 12",
    ],
    [
      "Sparse genres",
      `${smallestGenre.genre} has ${integer(smallestGenre.ratings)} training ratings, ` +
        `${percent(smallestGenre.ratings, windows.train.rows)} of the window`,
      "Expect split bias toward dense features; judge importance by permutation",
      "Phase 8",
    ],
    [
      "The movie list is not UTF-8",
      `${s.nonUtf8MovieLines} lines of movies.dat fail UTF-8 decoding`,
      "Read all three files as Latin-1",
      "Phase 1A",
    ],
  ];
}
