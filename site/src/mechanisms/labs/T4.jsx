import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { euclidean, nearest, relativeContrast } from "../lib/knn.js";
import { leastSquares } from "../lib/linalg.js";
import { rmse } from "../lib/metrics.js";
import { cumulative, pca } from "../lib/pca.js";
import { WIDE_NAMES, wideRatings } from "../lib/ratings.js";
import { curve, oneStandardError, rollingFolds } from "../lib/tuning.js";

const TRAIN = 240;
const K = 15;
const COUNTS = Array.from({ length: WIDE_NAMES.length }, (_, index) => index + 1);
const fewer = (a, b) => a.lambda < b.lambda;

// kNN on the first m components, with scaling and PCA fitted on the training rows only.
function knnOnComponents(trainRows, testRows, m, scale) {
  const fitted = pca(
    trainRows.map((row) => row.features),
    { scale },
  );
  const points = trainRows.map((row) => fitted.project(row.features, m));
  const ratings = trainRows.map((row) => row.rating);
  const guesses = testRows.map((row) => {
    const hits = nearest(points, fitted.project(row.features, m), K, euclidean);
    return hits.reduce((s, hit) => s + ratings[hit.index], 0) / hits.length;
  });
  return { fitted, points, guesses };
}

// Least squares on the first m components (principal components regression), the setting in
// which Jolliffe showed a low-variance component can carry the signal.
function regressionOnComponents(trainRows, testRows, m, scale) {
  const fitted = pca(
    trainRows.map((row) => row.features),
    { scale },
  );
  const design = (row) => [1, ...fitted.project(row.features, m)];
  const coef = leastSquares(
    trainRows.map(design),
    trainRows.map((row) => row.rating),
  );
  return testRows.map((row) => design(row).reduce((s, x, j) => s + x * coef[j], 0));
}

const plural = (count) => `${count} component${count === 1 ? "" : "s"}`;

export default function T4() {
  const [m, setM] = useState(3);
  const [scale, setScale] = useState(true);
  const [planted, setPlanted] = useState(false);

  const rows = useMemo(() => wideRatings({ seed: 81, n: 300, planted }), [planted]);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const fitted = useMemo(
    () =>
      pca(
        train.map((row) => row.features),
        { scale },
      ),
    [train, scale],
  );
  const shares = cumulative(fitted.values);
  const needed = [0.8, 0.9, 0.95].map((level) => shares.findIndex((share) => share >= level) + 1);

  const points = useMemo(
    () =>
      curve(COUNTS, rollingFolds(TRAIN, 5), (fold, count) => {
        const { guesses } = knnOnComponents(
          fold.train.map((index) => train[index]),
          fold.valid.map((index) => train[index]),
          count,
          scale,
        );
        return rmse(
          guesses,
          fold.valid.map((index) => train[index].rating),
        );
      }),
    [train, scale],
  );
  const { best, simplest } = useMemo(() => oneStandardError(points, fewer), [points]);
  const linear = useMemo(
    () =>
      curve(COUNTS, rollingFolds(TRAIN, 5), (fold, count) =>
        rmse(
          regressionOnComponents(
            fold.train.map((index) => train[index]),
            fold.valid.map((index) => train[index]),
            count,
            scale,
          ),
          fold.valid.map((index) => train[index].rating),
        ),
      ),
    [train, scale],
  );

  const timed = useMemo(() => {
    const started = performance.now();
    const result = knnOnComponents(train, later, m, scale);
    return { ...result, ms: performance.now() - started };
  }, [train, later, m, scale]);
  const laterRmse = rmse(
    timed.guesses,
    later.map((row) => row.rating),
  );
  const contrast = useMemo(() => {
    const values = later.slice(0, 20).map((row) =>
      relativeContrast(timed.points, timed.fitted.project(row.features, m), euclidean),
    );
    return values.reduce((s, v) => s + v, 0) / values.length;
  }, [later, timed, m]);
  const scores = useMemo(
    () => train.map((row) => fitted.project(row.features, 2)),
    [train, fitted],
  );

  const screeTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Variance of each component",
        x: COUNTS,
        y: fitted.values,
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Cumulative share",
        x: COUNTS,
        y: shares,
        yaxis: "y2",
        line: { color: colors.accent },
      },
    ],
    [fitted, shares],
  );
  const curveTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "kNN validation RMSE ± 1 SE",
        x: COUNTS,
        y: points.map((point) => point.error),
        error_y: { type: "data", array: points.map((point) => point.se), color: colors.line },
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Least squares on components",
        x: COUNTS,
        y: linear.map((point) => point.error),
        line: { color: colors.muted, dash: "dash" },
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
    ],
    [points, linear, best, simplest],
  );
  const projectionTraces = useCallback(
    () => [
      {
        type: "scatter",
        mode: "markers",
        name: "Training rows",
        x: scores.map((s) => s[0]),
        y: scores.map((s) => s[1]),
        marker: {
          size: 6,
          color: train.map((row) => row.rating),
          colorscale: "Viridis",
          showscale: true,
          colorbar: { title: { text: "Rating" } },
        },
      },
    ],
    [scores, train],
  );
  const screeLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Component" }, dtick: 1 },
      yaxis: { title: { text: "Variance" } },
      yaxis2: { overlaying: "y", side: "right", range: [0, 1.05], title: { text: "Share" } },
    }),
    [],
  );
  const curveLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Components kept" }, dtick: 1 },
      yaxis: { title: { text: "RMSE, time-ordered folds" } },
    }),
    [],
  );
  const projectionLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Component 1" } },
      yaxis: { title: { text: "Component 2" } },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Technique · Principal component analysis</h3>
      <p>
        PCA rotates the standardised features onto new axes ordered by how much of their variance
        each captures, and keeping the first few compresses the table for kNN. It never looks at
        the ratings: it keeps the most variance, and whether that is what predicts ratings is
        exactly what the validation curve tests.
      </p>
      <div className="lab-grid">
        <Plot traces={screeTraces} layout={screeLayout} label="Scree and cumulative share" />
        <Plot traces={curveTraces} layout={curveLayout} label="RMSE against components" />
      </div>
      <div className="controls">
        <Slider
          label="Components kept"
          value={m}
          min={1}
          max={COUNTS.length}
          step={1}
          onChange={setM}
          format={String}
        />
        <label className="control check">
          <input
            type="checkbox"
            checked={scale}
            onChange={(event) => setScale(event.target.checked)}
          />
          <span>Standardise before PCA</span>
        </label>
        <label className="control check">
          <input
            type="checkbox"
            checked={planted}
            onChange={(event) => setPlanted(event.target.checked)}
          />
          <span>Plant a signal in a low-variance direction</span>
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Variance kept</dt>
          <dd>
            {fixed(shares[m - 1] * 100, 1)}% with {m} components; 80%, 90% and 95% need{" "}
            {needed.join(", ")}
          </dd>
        </div>
        <div>
          <dt>kNN (k = {K}) on {plural(m)}</dt>
          <dd>
            Later-window RMSE {fixed(laterRmse)}; the folds favour {plural(best.lambda)} and the
            one-standard-error rule {plural(simplest.lambda)}. Fit and predict took{" "}
            {fixed(timed.ms, 1)} ms.
          </dd>
        </div>
        <div>
          <dt>Least squares on {plural(m)}</dt>
          <dd>
            Fold RMSE {fixed(linear[m - 1].error)}, against {fixed(linear.at(-1).error)} with all{" "}
            {COUNTS.length}
          </dd>
        </div>
        <div>
          <dt>Distance contrast at {m} components</dt>
          <dd>
            {fixed(contrast, 2)}, averaged over 20 later queries. Keeping every component
            reproduces the standardised distances exactly, since a rotation preserves them.
          </dd>
        </div>
      </dl>
      <h4>What the first two components are made of</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Feature</th>
              <th scope="col">Component 1</th>
              <th scope="col">Component 2</th>
            </tr>
          </thead>
          <tbody>
            {WIDE_NAMES.map((name, j) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{fixed(fitted.vectors[0][j])}</td>
                <td>{fixed(fitted.vectors[1][j])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Plot traces={projectionTraces} layout={projectionLayout} label="Rows on two components" />
      <p className="muted">
        Turn standardising off and the rating count, measured in large units, takes over the
        first component on its own. Plant the hidden signal and least squares on the components
        only recovers it among the last, lowest-variance components, because PCA ranked that
        direction last; kNN, which weighs each direction by its spread, barely sees it at all. A
        component's variance is not its relevance, so the pipeline measures error against
        components kept instead of assuming a number, fitting the scaler and PCA inside each
        fold. Seeded synthetic data:{" "}
        {train.length} training and {later.length} later ratings on five levels.
      </p>
    </article>
  );
}
