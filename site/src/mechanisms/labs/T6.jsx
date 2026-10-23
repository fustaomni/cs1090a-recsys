import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import {
  calibrationBins,
  calibrationSlope,
  decomposition,
  errorByLevel,
} from "../lib/calibration.js";
import { fixed } from "../lib/format.js";
import { rmse } from "../lib/metrics.js";
import { surfaceRatings, trueSurface } from "../lib/ratings.js";
import { grow, stepSurface, view } from "../lib/tree.js";
import { curve, oneStandardError, rollingFolds } from "../lib/tuning.js";

const FEATURES = ["user", "movie"];
const TRAIN = 240;
const MAX_SPLITS = 40;
const SPLITS = Array.from({ length: MAX_SPLITS + 1 }, (_, s) => s);
const RANGE = [-3, 3];
const fewer = (a, b) => a.lambda < b.lambda;

export default function T6() {
  const [splits, setSplits] = useState(0);
  const [noise, setNoise] = useState(0.7);
  const [seed, setSeed] = useState(191);

  const rows = useMemo(() => surfaceRatings({ seed, n: 300, noise }), [seed, noise]);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const valid = useMemo(() => rows.slice(TRAIN), [rows]);
  const tree = useMemo(() => grow(train, FEATURES, { minLeaf: 3 }), [train]);
  const model = view(tree, { steps: splits });

  const curves = useMemo(() => {
    const at = (set, s) => {
      const predict = view(tree, { steps: s }).predict;
      return rmse(set.map(predict), set.map((r) => r.rating));
    };
    return { train: SPLITS.map((s) => at(train, s)), valid: SPLITS.map((s) => at(valid, s)) };
  }, [tree, train, valid]);
  const points = useMemo(
    () =>
      curve(SPLITS, rollingFolds(TRAIN, 5), (fold, s) => {
        const foldTree = grow(
          fold.train.map((i) => train[i]),
          FEATURES,
          { minLeaf: 3 },
        );
        const predict = view(foldTree, { steps: s }).predict;
        const held = fold.valid.map((i) => train[i]);
        return rmse(held.map(predict), held.map((r) => r.rating));
      }),
    [train],
  );
  const { best, simplest } = useMemo(() => oneStandardError(points, fewer), [points]);

  const predictions = valid.map(model.predict);
  const actual = valid.map((r) => r.rating);
  const levels = errorByLevel(predictions, actual);
  const bins = calibrationBins(predictions, actual, 6);
  const slope = calibrationSlope(predictions, actual);

  const parts = useMemo(() => {
    const queries = surfaceRatings({ seed: 5, n: 60, noise });
    const trees = Array.from({ length: 12 }, (_, d) =>
      grow(surfaceRatings({ seed: 300 + d, n: TRAIN, noise }), FEATURES, { minLeaf: 3 }),
    );
    return [0, 1, 2, 4, 8, 16, 24, 32, 40].map((s) => ({
      s,
      ...decomposition(
        trees.map((t) => view(t, { steps: s }).predict),
        queries,
        trueSurface,
        noise * noise,
      ),
    }));
  }, [noise]);

  const thresholds = model.internal.map((n) => ({ feature: n.feature, value: n.threshold }));
  const surface = stepSurface(model.predict, "user", "movie", RANGE, RANGE, thresholds, {});

  const sceneTraces = useCallback(
    (colors) => {
      const segments = { x: [], y: [], z: [] };
      valid.forEach((r, i) => {
        segments.x.push(r.user, r.user, null);
        segments.y.push(r.movie, r.movie, null);
        segments.z.push(r.rating, predictions[i], null);
      });
      return [
        {
          type: "surface",
          ...surface,
          colorscale: "Viridis",
          cmin: 1,
          cmax: 5,
          opacity: 0.55,
          showscale: false,
          name: splits === 0 ? "A flat plane at the mean" : `Tree with ${splits} splits`,
        },
        {
          type: "scatter3d",
          mode: "lines",
          name: "Residuals, later window",
          ...segments,
          line: { color: colors.accent, width: 3 },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: "Later ratings",
          x: valid.map((r) => r.user),
          y: valid.map((r) => r.movie),
          z: actual,
          marker: { size: 3.5, color: colors.ink },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: "Training ratings",
          x: train.map((r) => r.user),
          y: train.map((r) => r.movie),
          z: train.map((r) => r.rating),
          marker: { size: 2, color: colors.muted, opacity: 0.5 },
        },
      ];
    },
    [surface, valid, predictions, actual, train, splits],
  );
  const curveTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines",
        name: "Training RMSE",
        x: SPLITS,
        y: curves.train,
        line: { color: colors.muted },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Fold RMSE ± 1 SE",
        x: SPLITS,
        y: points.map((p) => p.error),
        error_y: { type: "data", array: points.map((p) => p.se), color: colors.line },
        line: { color: colors.ink },
        marker: { size: 3 },
      },
      ...[
        { at: best, name: "Lowest" },
        { at: simplest, name: "Fewest within 1 SE" },
      ].map(({ at, name }) => ({
        type: "scatter",
        mode: "markers",
        name,
        x: [at.lambda],
        y: [at.error],
        marker: { size: 11, color: colors.accent, symbol: name === "Lowest" ? "circle" : "star" },
      })),
      {
        type: "scatter",
        mode: "markers",
        name: "Shown in 3D",
        x: [splits],
        y: [points[splits].error],
        marker: { size: 12, color: colors.ink, symbol: "diamond-open", line: { width: 2 } },
      },
    ],
    [curves, points, best, simplest, splits],
  );
  const levelTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Mean residual by true rating",
        x: levels.map((l) => l.level),
        y: levels.map((l) => l.mean),
        line: { color: colors.accent },
      },
    ],
    [levels],
  );
  const calibrationTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Mean rating per predicted-value bin",
        x: bins.map((b) => b.predicted),
        y: bins.map((b) => b.actual),
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Perfect calibration",
        x: [1, 5],
        y: [1, 5],
        line: { color: colors.muted, dash: "dot" },
      },
    ],
    [bins],
  );
  const partTraces = useCallback(
    (colors) =>
      [
        ["bias", "Bias²", colors.accent],
        ["variance", "Variance", colors.ink],
        ["noise", "Noise", colors.muted],
      ].map(([key, name, color]) => ({
        type: "scatter",
        mode: "lines+markers",
        name,
        x: parts.map((p) => p.s),
        y: parts.map((p) => p[key]),
        line: { color },
      })),
    [parts],
  );
  const scene = useMemo(
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
  const axes = (x, y) => ({ xaxis: { title: { text: x } }, yaxis: { title: { text: y } } });
  const curveLayout = useMemo(() => axes("Tree splits (complexity)", "RMSE"), []);
  const levelLayout = useMemo(() => axes("True rating", "Mean residual, predicted − true"), []);
  const calibrationLayout = useMemo(
    () => axes("Mean predicted rating", "Mean actual rating"),
    [],
  );
  const partLayout = useMemo(() => axes("Tree splits", "Squared error, synthetic only"), []);
  const one = levels[0];
  const five = levels[4];

  return (
    <article className="lab">
      <h3>Technique · The bias–variance trade-off</h3>
      <p>
        Complexity here is a named hyperparameter: the number of splits in a regression tree.
        With none, every prediction is the training mean, a flat plane. Each later rating is
        joined to its prediction by a vertical residual. As splits are added, training error
        keeps falling, while error on held-out rows falls and then rises again: that curve is
        the evidence, computed, with no need for the true function.
      </p>
      <Plot traces={sceneTraces} layout={scene} label="Predictions and residuals" height={460} />
      <div className="controls">
        <Slider
          label="Tree splits"
          value={splits}
          min={0}
          max={MAX_SPLITS}
          step={1}
          onChange={setSplits}
          format={String}
        />
        <Slider
          label="Noise in the ratings"
          value={noise}
          min={0.3}
          max={1.2}
          step={0.05}
          onChange={setNoise}
        />
        <button type="button" className="action quiet" onClick={() => setSeed(seed + 1)}>
          New sample
        </button>
      </div>
      <dl className="readouts">
        <div>
          <dt>RMSE at {splits} splits</dt>
          <dd>
            Training {fixed(curves.train[splits])}, later window {fixed(curves.valid[splits])};
            folds favour {best.lambda} splits and the one-standard-error rule {simplest.lambda}
          </dd>
        </div>
        <div>
          <dt>Calibration slope</dt>
          <dd>
            {Number.isFinite(slope) ? fixed(slope, 2) : "undefined for a constant"}: near 1 the
            shrinkage is the expected kind; well above 1 the predictions are flatter than the data
            supports; below 1 they spread wider than it supports, the mark of overfitting
          </dd>
        </div>
        <div>
          <dt>Mean residual at 1★ and 5★</dt>
          <dd>
            {fixed(one.mean, 2)} and {fixed(five.mean, 2)}: low ratings are over-predicted and
            high ones under-predicted even by the best squared-error predictor
          </dd>
        </div>
      </dl>
      <Plot traces={curveTraces} layout={curveLayout} label="Error by complexity" height={300} />
      <div className="lab-grid">
        <Plot traces={levelTraces} layout={levelLayout} label="Error by true rating" />
        <Plot traces={calibrationTraces} layout={calibrationLayout} label="Calibration" />
      </div>
      <h4>Synthetic only: bias², variance and noise across twelve independent datasets</h4>
      <Plot traces={partTraces} layout={partLayout} label="Decomposition" height={300} />
      <p className="muted">
        The decomposition needs the true function, which only seeded data has; on MovieLens the
        curve above is the evidence. Error by true rating always slants, so Phase 12 decides
        whether to accept the shrinkage by calibration, binned by predicted value. Seeded
        synthetic data: {train.length} training and {valid.length} later ratings on five levels.
      </p>
      <Provenance
        data="Synthetic ratings from a known true surface, generated in this page: surfaceRatings({ seed: 191, n: 300 }), seed raised by New sample; no real ratings"
        split="The first 240 rows train; the remaining 60 are the later window"
        features="user, movie"
        method="Regression tree, with tree splits as the complexity"
      />
    </article>
  );
}
