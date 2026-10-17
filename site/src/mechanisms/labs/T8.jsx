import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { ensemblePredict, forest } from "../lib/ensemble.js";
import { fixed } from "../lib/format.js";
import {
  outsideSupport,
  permutationRises,
  permuted,
  rmseOf,
  shares,
} from "../lib/importance.js";
import { mulberry32 } from "../lib/random.js";
import { forestRatings } from "../lib/ratings.js";
import { impurityImportance } from "../lib/tree.js";

const FEATURES = ["user", "movie", "genre", "noise"];
const LABELS = { user: "user history", movie: "movie history", genre: "genre", noise: "noise" };
const PARTNER = { user: "movie", movie: "user", genre: "user", noise: "user" };
const TRAIN = 220;
const SETTINGS = { trees: 30, mtry: 2, minLeaf: 3, seed: 13 };
const METHODS = ["plain", "conditional", "drop"];
const METHOD_LABELS = {
  plain: "Plain permutation",
  conditional: "Conditional permutation",
  drop: "Drop-column refit",
};
const HYPOTHESIS = { user: 0.35, movie: 0.3 };

function spread(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const at = (q) => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
  return { mean, low: at(0.025), high: at(0.975) };
}

export default function T8() {
  const [rho, setRho] = useState(0.6);
  const [repeats, setRepeats] = useState(10);
  const [shown, setShown] = useState("user");
  const [method, setMethod] = useState("plain");

  const rows = useMemo(() => forestRatings({ seed: 121, n: 300, rho }), [rho]);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const members = useMemo(() => forest(train, FEATURES, SETTINGS), [train]);
  const predict = useCallback((row) => ensemblePredict(members, row), [members]);
  const base = rmseOf(predict, later);

  const results = useMemo(() => {
    const rng = mulberry32(31);
    const rises = {
      plain: FEATURES.map((f) => permutationRises(predict, later, f, rng, repeats)),
      conditional: FEATURES.map((f) =>
        permutationRises(predict, later, f, rng, repeats, PARTNER[f]),
      ),
    };
    const drop = FEATURES.map((f) => {
      const kept = FEATURES.filter((g) => g !== f);
      const refit = forest(train, kept, SETTINGS);
      return rmseOf((row) => ensemblePredict(refit, row), later) - base;
    });
    return { ...rises, drop: drop.map((value) => [value]) };
  }, [predict, later, train, repeats, base]);
  const impurity = useMemo(() => {
    const totals = FEATURES.map(() => 0);
    for (const member of members) {
      impurityImportance(member.tree, FEATURES).forEach((v, j) => {
        totals[j] += v / members.length;
      });
    }
    return totals;
  }, [members]);

  const shareRuns = (name) =>
    results[name][0].map((_, r) => shares(FEATURES.map((_, j) => results[name][j][r])));
  const shareSummary = Object.fromEntries(
    METHODS.map((name) => {
      const runs = shareRuns(name);
      return [name, FEATURES.map((_, j) => spread(runs.map((run) => run[j])))];
    }),
  );

  const radius = useMemo(() => {
    const nearest = train.map((row, i) => {
      let best = Infinity;
      train.forEach((other, k) => {
        if (k === i) return;
        best = Math.min(best, Math.hypot(row.user - other.user, row.movie - other.movie));
      });
      return best;
    });
    return nearest.sort((a, b) => a - b)[Math.floor(0.95 * nearest.length)];
  }, [train]);
  const moved = useMemo(
    () =>
      permuted(later, shown, mulberry32(77), method === "conditional" ? PARTNER[shown] : null),
    [later, shown, method],
  );
  const outsidePlain = useMemo(
    () => outsideSupport(train, permuted(later, "user", mulberry32(5)), ["user", "movie"], radius),
    [train, later, radius],
  );
  const outsideConditional = useMemo(
    () =>
      outsideSupport(
        train,
        permuted(later, "user", mulberry32(5), "movie"),
        ["user", "movie"],
        radius,
      ),
    [train, later, radius],
  );

  const sceneTraces = useCallback(
    (colors) => {
      const segments = { x: [], y: [], z: [] };
      later.forEach((row, i) => {
        segments.x.push(row.user, moved[i].user, null);
        segments.y.push(row.movie, moved[i].movie, null);
        segments.z.push(row.rating, predict(moved[i]), null);
      });
      return [
        {
          type: "scatter3d",
          mode: "lines",
          name: "Truth to moved prediction",
          ...segments,
          line: { color: colors.line, width: 2 },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: "Later ratings (fixed)",
          x: later.map((row) => row.user),
          y: later.map((row) => row.movie),
          z: later.map((row) => row.rating),
          marker: { size: 3.5, color: colors.ink },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: `Predictions after shuffling ${LABELS[shown]}`,
          x: moved.map((row) => row.user),
          y: moved.map((row) => row.movie),
          z: moved.map(predict),
          marker: { size: 3.5, color: colors.accent },
        },
      ];
    },
    [later, moved, predict, shown],
  );
  const sceneLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User history" } },
        yaxis: { title: { text: "Movie history" } },
        zaxis: { title: { text: "Rating" }, range: [1, 5] },
        camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  const userShare = shareSummary[method][0];
  const movieShare = shareSummary[method][1];
  const covers = (s, value) => s.low <= value && value <= s.high;

  return (
    <article className="lab">
      <h3>Technique · Variable importance</h3>
      <p>
        Shuffle one feature in the later rows and the truth stays put while each prediction moves
        to wherever the model sends the new inputs; the rise in error is that feature's
        importance. With correlated features a plain shuffle invents combinations the training
        data never contained, so the model extrapolates. A conditional shuffle within strata of
        the correlated feature keeps combinations realistic, and refitting without the feature
        asks a different question: what is lost if it is gone.
      </p>
      <Plot traces={sceneTraces} layout={sceneLayout} label="After a shuffle" height={460} />
      <div className="controls">
        <label className="control">
          <span>Feature to shuffle</span>
          <select value={shown} onChange={(event) => setShown(event.target.value)}>
            {["user", "movie", "genre"].map((f) => (
              <option key={f} value={f}>
                {LABELS[f]}
              </option>
            ))}
          </select>
        </label>
        <label className="control">
          <span>Method</span>
          <select value={method} onChange={(event) => setMethod(event.target.value)}>
            {METHODS.map((m) => (
              <option key={m} value={m}>
                {METHOD_LABELS[m]}
              </option>
            ))}
          </select>
        </label>
        <Slider
          label="Correlation of user and movie history ρ"
          value={rho}
          min={0}
          max={0.9}
          step={0.1}
          onChange={setRho}
        />
        <Slider
          label="Shuffles per feature"
          value={repeats}
          min={5}
          max={30}
          step={5}
          onChange={setRepeats}
          format={String}
        />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Feature</th>
              <th scope="col">Impurity share (training)</th>
              {METHODS.map((m) => (
                <th scope="col" key={m}>
                  {METHOD_LABELS[m]}: rise in RMSE
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((f, j) => (
              <tr key={f}>
                <th scope="row">{LABELS[f]}</th>
                <td>{fixed(impurity[j] * 100, 0)}%</td>
                {METHODS.map((m) => {
                  const s = spread(results[m][j]);
                  return (
                    <td key={m}>
                      {fixed(s.mean)}
                      {m !== "drop" && ` (${fixed(s.low)} to ${fixed(s.high)})`}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="readouts">
        <div>
          <dt>Baseline</dt>
          <dd>Later-window RMSE {fixed(base)} before any shuffle</dd>
        </div>
        <div>
          <dt>Shuffled points outside the training data</dt>
          <dd>
            {fixed(outsidePlain * 100, 0)}% after a plain shuffle of user history,{" "}
            {fixed(outsideConditional * 100, 0)}% after a conditional one
          </dd>
        </div>
        <div>
          <dt>The 35% / 30% user-against-movie split, tested</dt>
          <dd>
            With {METHOD_LABELS[method].toLowerCase()}, user history takes{" "}
            {fixed(userShare.mean * 100, 0)}% ({fixed(userShare.low * 100, 0)} to{" "}
            {fixed(userShare.high * 100, 0)}) and movie history {fixed(movieShare.mean * 100, 0)}% (
            {fixed(movieShare.low * 100, 0)} to {fixed(movieShare.high * 100, 0)}) of the summed
            rises. 35% is {covers(userShare, HYPOTHESIS.user) ? "inside" : "outside"} the user
            interval and 30% is {covers(movieShare, HYPOTHESIS.movie) ? "inside" : "outside"} the
            movie interval.
          </dd>
        </div>
      </dl>
      <p className="muted">
        Shares are each feature's rise in RMSE over the sum of positive rises, an explicit
        normalisation; the published split may have used a different measure, so agreement is
        only meaningful if the measures match. Intervals here are over shuffles, model randomness
        only; on the project data the user-clustered bootstrap adds the uncertainty of the data.
        This lab runs on seeded synthetic ratings ({train.length} training, {later.length}{" "}
        later), so its verdict is about them, not about MovieLens.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: forestRatings({ seed: 121, n: 300 }); no real ratings"
        split="The first 220 rows train; the remaining 80 are the later window"
        features="user, movie, genre, noise"
        method="Random forest with 30 trees, mtry 2, minimum leaf 3, seed 13"
      />
    </article>
  );
}
