// site/src/mechanisms/lib/signflip.js
// Technique 12, the user-level sign-flip permutation test (A.246): each user's paired
// error differences (model A minus model B) form one block; under the null of no difference
// each block's sign is arbitrary, so the reference distribution is the mean over users of
// every sign pattern, enumerated exactly. With n users the smallest two-sided p is 2 / 2^n.
import { mulberry32, normal } from "./random.js";

export const SIGNFLIP = { ratings: 10, effect: -0.15, userSpread: 0.12, noise: 0.25 };

export function blockData({ seed = 171, users = 5 } = {}) {
  const rng = mulberry32(seed);
  return Array.from({ length: users }, (_, user) => {
    const shift = SIGNFLIP.effect + SIGNFLIP.userSpread * normal(rng);
    const deltas = Array.from({ length: SIGNFLIP.ratings }, () => shift + SIGNFLIP.noise * normal(rng));
    return { user: user + 1, deltas };
  });
}

const mean = (values) => values.reduce((total, value) => total + value, 0) / values.length;

export function userMeans(blocks) {
  return blocks.map((block) => mean(block.deltas));
}

export function statistic(means, signs) {
  return mean(means.map((value, index) => value * signs[index]));
}

export function exactNull(means) {
  const patterns = 2 ** means.length;
  const values = [];
  for (let mask = 0; mask < patterns; mask += 1) {
    const signs = means.map((_, index) => ((mask >> index) & 1 ? -1 : 1));
    values.push(statistic(means, signs));
  }
  return values;
}

export function exactP(means) {
  const observed = Math.abs(mean(means));
  const values = exactNull(means);
  return values.filter((value) => Math.abs(value) >= observed - 1e-12).length / values.length;
}

export function pFloor(users) {
  return 2 / 2 ** users;
}

export function rowLevelP(blocks, { draws = 4000, seed = 173 } = {}) {
  const rng = mulberry32(seed);
  const rows = blocks.flatMap((block) => block.deltas);
  const observed = Math.abs(mean(rows));
  let extreme = 0;
  for (let draw = 0; draw < draws; draw += 1) {
    let total = 0;
    for (const value of rows) total += rng() < 0.5 ? -value : value;
    if (Math.abs(total / rows.length) >= observed - 1e-12) extreme += 1;
  }
  return (extreme + 1) / (draws + 1);
}

export function skewness(values) {
  const center = mean(values);
  const spread = Math.sqrt(mean(values.map((value) => (value - center) ** 2)));
  return spread > 0 ? mean(values.map((value) => ((value - center) / spread) ** 3)) : 0;
}

export function randomSigns(users, seed) {
  const rng = mulberry32(seed);
  return Array.from({ length: users }, () => (rng() < 0.5 ? -1 : 1));
}
