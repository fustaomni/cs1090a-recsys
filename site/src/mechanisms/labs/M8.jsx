import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import {
  blockSurface,
  ensemblePredict,
  forest,
  outOfBag,
  varianceAcrossDatasets,
} from "../lib/ensemble.js";
import { fixed } from "../lib/format.js";
import { steps } from "../lib/grid.js";
import { rmse } from "../lib/metrics.js";
import { forestRatings } from "../lib/ratings.js";
import { stepSurface } from "../lib/tree.js";

const FEATURES = ["user", "movie", "genre", "noise"];
const TRAIN = 200;
const MAX_TREES = 50;
const RANGE = [-2.5, 2.5];
const FIXED = { genre: 0, noise: 0 };
const SLICE = steps(-2.5, 2.5, 161);
const COUNTS = [1, 2, 3, 5, 8, 12, 20, 30, 40, 50];
const SHOWN = 8;

export default function M8() {
  const [count, setCount] = useState(1);
  const [draw, setDraw] = useState(1);
  const [movie, setMovie] = useState(0.5);

  const rows = useMemo(() => forestRatings({ seed: 101, n: 240 }), []);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const members = useMemo(
    () => forest(train, FEATURES, { trees: MAX_TREES, minLeaf: 3, seed: draw }),
    [train, draw],
  );
  const predict = useCallback((row) => ensemblePredict(members, row, count), [members, count]);

  const surface = useMemo(() => {
    if (count === 1) {
      const thresholds = members[0].model.internal.map((n) => ({
        feature: n.feature,
        value: n.threshold,
      }));
      return stepSurface(predict, "user", "movie", RANGE, RANGE, thresholds, FIXED);
    }
    return blockSurface(predict, "user", "movie", RANGE, RANGE, 48, FIXED);
  }, [members, count, predict]);

  const variance = useMemo(
    () =>
      varianceAcrossDatasets(
        (seed) => forestRatings({ seed, n: TRAIN }),
        FEATURES,
        forestRatings({ seed: 9, n: 20 }),
        { datasets: 6, trees: 30, minLeaf: 3 },
      ),
    [],
  );
  const theory = variance.perB.map(
    (_, b) => variance.rho * variance.sigma2 + ((1 - variance.rho) * variance.sigma2) / (b + 1),
  );

  const curves = useMemo(() => {
    const actual = train.map((row) => row.rating);
    const laterActual = later.map((row) => row.rating);
    return COUNTS.map((b) => {
      const oob = outOfBag(members, train, b);
      const kept = oob
        .map((value, i) => [value, actual[i]])
        .filter(([value]) => !Number.isNaN(value));
      return {
        b,
        oob: rmse(
          kept.map(([value]) => value),
          kept.map(([, y]) => y),
        ),
        later: rmse(
          later.map((row) => ensemblePredict(members, row, b)),
          laterActual,
        ),
      };
    });
  }, [members, train, later]);

  const sliceRows = SLICE.map((user) => ({ ...FIXED, user, movie }));
  const perTree = members.slice(0, count).map((m) => sliceRows.map((row) => m.model.predict(row)));
  const mean = sliceRows.map((_, i) => perTree.reduce((s, t) => s + t[i], 0) / perTree.length);
  const sd = sliceRows.map((_, i) =>
    Math.sqrt(perTree.reduce((s, t) => s + (t[i] - mean[i]) ** 2, 0) / perTree.length),
  );
  const outsideShare = 1 - members[0].inBag.size / TRAIN;
  const oobNow = outOfBag(members, train, count);
  const oobKept = oobNow
    .map((value, i) => [value, train[i].rating])
    .filter(([value]) => !Number.isNaN(value));

  const surfaceTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        ...surface,
        colorscale: "Viridis",
        cmin: 1,
        cmax: 5,
        opacity: 0.92,
        showscale: false,
        name: count === 1 ? "One deep tree" : `Average of ${count} trees`,
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Training ratings",
        x: train.map((row) => row.user),
        y: train.map((row) => row.movie),
        z: train.map((row) => row.rating),
        marker: { size: 2.5, color: colors.muted, opacity: 0.5 },
      },
    ],
    [surface, count, train],
  );
  const sliceTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines",
        name: "+1 SD",
        x: SLICE,
        y: mean.map((m, i) => m + sd[i]),
        line: { width: 0, color: colors.accent },
        showlegend: false,
      },
      {
        type: "scatter",
        mode: "lines",
        name: "± 1 SD across trees",
        x: SLICE,
        y: mean.map((m, i) => m - sd[i]),
        fill: "tonexty",
        fillcolor: "rgba(127,127,127,0.25)",
        line: { width: 0, color: colors.accent },
      },
      ...perTree.slice(0, SHOWN).map((values, k) => ({
        type: "scatter",
        mode: "lines",
        name: k === 0 ? "Individual trees" : undefined,
        showlegend: k === 0,
        x: SLICE,
        y: values,
        line: { color: colors.muted, width: 1, shape: "hv" },
      })),
      {
        type: "scatter",
        mode: "lines",
        name: "Bagged mean",
        x: SLICE,
        y: mean,
        line: { color: colors.accent, width: 3, shape: "hv" },
      },
    ],
    [mean, sd, perTree],
  );
  const varianceTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Across 6 datasets",
        x: variance.perB.map((_, b) => b + 1),
        y: variance.perB,
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "ρσ² + (1 − ρ)σ² / B",
        x: theory.map((_, b) => b + 1),
        y: theory,
        line: { color: colors.accent, dash: "dash" },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Floor ρσ²",
        x: [1, variance.perB.length],
        y: [variance.floor, variance.floor],
        line: { color: colors.muted, dash: "dot" },
      },
    ],
    [variance, theory],
  );
  const oobTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Out-of-bag RMSE",
        x: curves.map((c) => c.b),
        y: curves.map((c) => c.oob),
        line: { color: colors.accent },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Later-window RMSE",
        x: curves.map((c) => c.b),
        y: curves.map((c) => c.later),
        line: { color: colors.ink },
      },
    ],
    [curves],
  );
  const surfaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User history" } },
        yaxis: { title: { text: "Movie history" } },
        zaxis: { title: { text: "Predicted rating" }, range: [1, 5] },
        camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );
  const sliceLayout = useMemo(
    () => ({
      xaxis: { title: { text: "User history, at the chosen movie history" } },
      yaxis: { title: { text: "Predicted rating" }, range: [1, 5] },
    }),
    [],
  );
  const varianceLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Trees averaged, B" } },
      yaxis: { title: { text: "Variance of the prediction" }, rangemode: "tozero" },
    }),
    [],
  );
  const oobLayout = useMemo(
    () => ({ xaxis: { title: { text: "Trees, B" } }, yaxis: { title: { text: "RMSE" } } }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 8 · Bagging</h3>
      <p>
        Bagging grows many deep trees, each on a bootstrap sample of the rows, and averages them.
        Each tree is a step function with high variance and low bias; their average is still a
        step function, only with finer steps. Averaging lowers variance but not bias, and because
        the trees are grown from the same data they are correlated, so the variance falls toward
        a floor, not to zero.
      </p>
      <Plot traces={surfaceTraces} layout={surfaceLayout} label="Bagged surface" height={460} />
      <div className="controls">
        <Slider
          label="Trees averaged, B"
          value={count}
          min={1}
          max={MAX_TREES}
          step={1}
          onChange={setCount}
          format={String}
        />
        <Slider
          label="Movie history for the slice"
          value={movie}
          min={-2}
          max={2}
          step={0.1}
          onChange={setMovie}
        />
        <button type="button" className="action quiet" onClick={() => setDraw(draw + 1)}>
          New bootstrap seed
        </button>
      </div>
      <dl className="readouts">
        <div>
          <dt>Variance across datasets</dt>
          <dd>
            One tree σ² = {fixed(variance.sigma2, 3)}; correlation between trees ρ ={" "}
            {fixed(variance.rho, 2)}; so averaging can only reach ρσ² ={" "}
            {fixed(variance.floor, 3)}.
          </dd>
        </div>
        <div>
          <dt>One bootstrap sample</dt>
          <dd>
            Tree 1 never saw {fixed(outsideShare * 100, 1)}% of the {TRAIN} rows; (1 − 1/n)ⁿ →
            1/e ≈ 36.8%.
          </dd>
        </div>
        <div>
          <dt>RMSE with {count} trees</dt>
          <dd>
            Training {fixed(rmse(train.map(predict), train.map((row) => row.rating)))}, out of
            bag{" "}
            {oobKept.length > 0
              ? fixed(
                  rmse(
                    oobKept.map(([value]) => value),
                    oobKept.map(([, y]) => y),
                  ),
                )
              : "n/a"}
            , later window {fixed(rmse(later.map(predict), later.map((row) => row.rating)))}
          </dd>
        </div>
      </dl>
      <div className="lab-grid">
        <Plot traces={sliceTraces} layout={sliceLayout} label="Trees along one slice" />
        <Plot traces={varianceTraces} layout={varianceLayout} label="Variance against B" />
      </div>
      <Plot traces={oobTraces} layout={oobLayout} label="Out-of-bag and later RMSE" height={300} />
      <p className="muted">
        Out-of-bag error predicts each training row only with trees that left it out, which makes
        it a random-split estimate: it ignores time, so the later window is the honest number to
        compare it with. Seeded synthetic data: {train.length} training and {later.length} later
        ratings on five levels.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: forestRatings({ seed: 101, n: 240 }), query rows forestRatings({ seed: 9, n: 20 }); no real ratings"
        split="The first 200 rows train; the remaining 40 are the later window"
        features="user, movie, genre, noise"
        method="Bagged regression trees on bootstrap resamples"
      />
    </article>
  );
}
