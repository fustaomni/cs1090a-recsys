// site/src/mechanisms/lib/oob.js
// Technique 7: one seed's estimates of the same forest's error. Out of bag and random three-fold
// cross-validation on the training period; a random split of the later window, one half added
// to training and the other held out (within-period random); and the temporal score of the
// forest trained on the past, over the whole later window and over that same held-out half, so
// the gap is decomposed on identical rows.
import { ensemblePredict, forest, outOfBag } from "./ensemble.js";
import { randomFolds, rmseOf } from "./importance.js";
import { mulberry32 } from "./random.js";

export const FEATURES = ["user", "movie", "genre", "noise"];
export const SETTINGS = { trees: 30, mtry: 2, minLeaf: 5 };

export function oobRmse(members, rows, count) {
  const values = outOfBag(members, rows, count);
  const kept = values.map((v, i) => [v, rows[i].rating]).filter(([v]) => !Number.isNaN(v));
  return Math.sqrt(kept.reduce((s, [v, y]) => s + (v - y) ** 2, 0) / kept.length);
}

export function estimates(train, later, seed) {
  const members = forest(train, FEATURES, { ...SETTINGS, seed });
  const rng = mulberry32(500 + seed);
  let squares = 0;
  for (const fold of randomFolds(train.length, 3, rng)) {
    const held = new Set(fold);
    const fitted = forest(
      train.filter((_, i) => !held.has(i)),
      FEATURES,
      { ...SETTINGS, trees: 15, seed },
    );
    for (const i of fold) squares += (ensemblePredict(fitted, train[i]) - train[i].rating) ** 2;
  }
  const [inside, outside] = randomFolds(later.length, 2, rng);
  const pooled = forest(
    [...train, ...inside.map((i) => later[i])],
    FEATURES,
    { ...SETTINGS, seed },
  );
  const held = outside.map((i) => later[i]);
  const past = (row) => ensemblePredict(members, row);
  return {
    members,
    held: outside,
    values: [
      oobRmse(members, train),
      Math.sqrt(squares / train.length),
      rmseOf((row) => ensemblePredict(pooled, row), held),
      rmseOf(past, later),
    ],
    temporalHeld: rmseOf(past, held),
  };
}
