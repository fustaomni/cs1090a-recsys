import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps, surface } from "../lib/grid.js";
import { rmse } from "../lib/metrics.js";
import { eigen2, moments, prepared, ridge } from "../lib/penalized.js";
import { mulberry32, resample } from "../lib/random.js";
import { ratings } from "../lib/ratings.js";
import { curve, logGrid, oneStandardError, rollingFolds } from "../lib/tuning.js";

const KEYS = ["user", "movie"];
const B = steps(-0.3, 1.0, 41);
const LAMBDAS = logGrid(100, 0.001, 60);
const TRAIN = 120;
const RESAMPLES = 30;

function scorer(rows) {
  return (indices, lambda) => {
    const picked = indices.train.map((index) => rows[index]);
    const { standard, ybar, xs, ys } = prepared(picked, KEYS);
    const coef = ridge(moments(xs, ys), lambda);
    const later = indices.valid.map((index) => rows[index]);
    const guess = (row) => ybar + standard(row).reduce((s, x, j) => s + x * coef[j], 0);
    const guesses = later.map(guess);
    return rmse(guesses, later.map((row) => row.rating));
  };
}

export default function M4() {
  const [rho, setRho] = useState(0.9);
  const [exponent, setExponent] = useState(-1);
  const [draw, setDraw] = useState(1);
  const lambda = 10 ** exponent;

  const rows = useMemo(() => ratings({ seed: 51, n: 150, rho }), [rho]);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const fitted = useMemo(() => prepared(train, KEYS), [train]);
  const sums = useMemo(() => moments(fitted.xs, fitted.ys), [fitted]);
  const syy = useMemo(
    () => fitted.ys.reduce((s, y) => s + y * y, 0) / fitted.ys.length,
    [fitted],
  );
  const cost = useCallback(
    (b, at) => {
      const quadratic = b.reduce(
        (s, bi, i) => s + bi * b.reduce((t, bj, j) => t + sums.gram[i][j] * bj, 0),
        0,
      );
      const linear = b.reduce((s, bi, i) => s + bi * sums.cross[i], 0);
      return 0.5 * (syy - 2 * linear + quadratic) + (at / 2) * (b[0] ** 2 + b[1] ** 2);
    },
    [sums, syy],
  );

  const ols = useMemo(() => ridge(sums, 0), [sums]);
  const coef = ridge(sums, lambda);
  const path = useMemo(() => LAMBDAS.map((at) => ridge(sums, at)), [sums]);
  const bowl = useMemo(() => surface(B, B, (b1, b2) => cost([b1, b2], lambda)), [cost, lambda]);
  const points = useMemo(
    () => curve(LAMBDAS, rollingFolds(TRAIN, 5), scorer(train)),
    [train],
  );
  const { best, simplest } = useMemo(() => oneStandardError(points), [points]);
  const cloud = useMemo(() => {
    const rng = mulberry32(2000 + draw);
    return Array.from({ length: RESAMPLES }, () => {
      const picked = resample(rng, train.length).map((index) => train[index]);
      const sample = prepared(picked, KEYS);
      const sampleSums = moments(sample.xs, sample.ys);
      return { ols: ridge(sampleSums, 0), ridge: ridge(sampleSums, lambda) };
    });
  }, [draw, train, lambda]);

  const [large, small] = eigen2(sums.gram);
  const df = large / (large + lambda) + small / (small + lambda);
  const predict = (b) => (row) =>
    fitted.ybar + fitted.standard(row).reduce((s, x, j) => s + x * b[j], 0);
  const score = (set, b) => rmse(set.map(predict(b)), set.map((row) => row.rating));
  const spread = (key, k) => {
    const values = cloud.map((fit) => fit[key][k]);
    const centre = values.reduce((s, v) => s + v, 0) / values.length;
    return Math.sqrt(values.reduce((s, v) => s + (v - centre) ** 2, 0) / values.length);
  };

  const bowlTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        x: B,
        y: B,
        z: bowl,
        colorscale: "Viridis",
        opacity: 0.7,
        showscale: false,
        name: "Ridge objective",
      },
      {
        type: "scatter3d",
        mode: "lines",
        name: "Ridge minimum as λ grows",
        x: path.map((b) => b[0]),
        y: path.map((b) => b[1]),
        z: path.map((b) => cost(b, lambda)),
        line: { color: colors.ink, width: 5 },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Resampled least squares",
        x: cloud.map((fit) => fit.ols[0]),
        y: cloud.map((fit) => fit.ols[1]),
        z: cloud.map(() => 0),
        marker: { size: 3, color: colors.muted },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Resampled ridge",
        x: cloud.map((fit) => fit.ridge[0]),
        y: cloud.map((fit) => fit.ridge[1]),
        z: cloud.map(() => 0),
        marker: { size: 3, color: colors.accent },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Least squares",
        x: [ols[0]],
        y: [ols[1]],
        z: [cost(ols, lambda)],
        marker: { size: 6, color: colors.ink, symbol: "diamond" },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Ridge at this λ",
        x: [coef[0]],
        y: [coef[1]],
        z: [cost(coef, lambda)],
        marker: { size: 7, color: colors.accent },
      },
    ],
    [bowl, path, cloud, ols, coef, cost, lambda],
  );
  const bowlLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "b1 (user history)" } },
        yaxis: { title: { text: "b2 (movie history)" } },
        zaxis: { title: { text: "Objective" } },
        camera: { eye: { x: 1.5, y: -1.7, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  const pathTraces = useCallback(
    (colors) => [
      ...[0, 1].map((k) => ({
        type: "scatter",
        mode: "lines",
        name: k === 0 ? "b1, user" : "b2, movie",
        x: LAMBDAS,
        y: path.map((b) => b[k]),
        line: { color: k === 0 ? colors.accent : colors.ink, width: 2.5 },
      })),
      {
        type: "scatter",
        mode: "lines",
        name: "This λ",
        x: [lambda, lambda],
        y: [Math.min(0, ...ols), Math.max(...ols)],
        line: { color: colors.muted, dash: "dot" },
      },
    ],
    [path, lambda, ols],
  );
  const curveTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Validation RMSE ± 1 SE",
        x: points.map((point) => point.lambda),
        y: points.map((point) => point.error),
        error_y: { type: "data", array: points.map((point) => point.se), color: colors.line },
        marker: { size: 4, color: colors.ink },
        line: { color: colors.ink },
      },
      ...[
        { at: best, name: "λ min" },
        { at: simplest, name: "λ 1-SE" },
      ].map(({ at, name }) => ({
        type: "scatter",
        mode: "markers",
        name,
        x: [at.lambda],
        y: [at.error],
        marker: { size: 11, color: colors.accent, symbol: name === "λ min" ? "circle" : "star" },
      })),
    ],
    [points, best, simplest],
  );
  const logLayout = (title) => ({
    xaxis: { type: "log", title: { text: "λ (log scale)" } },
    yaxis: { title: { text: title } },
  });
  const pathLayout = useMemo(() => logLayout("Coefficient"), []);
  const curveLayout = useMemo(() => logLayout("Validation RMSE, time-ordered folds"), []);

  return (
    <article className="lab">
      <h3>Model 4 · Ridge regression</h3>
      <p>
        Ridge adds λ‖b‖² to the least squares objective, which rounds the valley of correlated
        predictors into a bowl. Its minimum, the dark line, slides toward zero as λ grows and pulls
        the two coefficients toward each other without ever reaching zero. Resampling shows why
        that helps: the least squares fits scatter along the valley while the ridge fits stay
        close together.
      </p>
      <Plot traces={bowlTraces} layout={bowlLayout} label="Ridge objective surface" height={480} />
      <div className="lab-grid">
        <Plot traces={pathTraces} layout={pathLayout} label="Ridge coefficient path" />
        <Plot traces={curveTraces} layout={curveLayout} label="Validation curve" />
      </div>
      <div className="controls">
        <Slider
          label="λ"
          value={exponent}
          min={-3}
          max={2}
          step={0.05}
          onChange={setExponent}
          format={(value) => fixed(10 ** value, 3)}
        />
        <Slider
          label="Correlation of the predictors ρ"
          value={rho}
          min={0}
          max={0.95}
          step={0.05}
          onChange={setRho}
        />
        <div className="button-row">
          <button
            type="button"
            className="action"
            onClick={() => setExponent(Math.log10(simplest.lambda))}
          >
            Select by the 1-SE rule
          </button>
          <button type="button" className="action quiet" onClick={() => setDraw(draw + 1)}>
            Resample
          </button>
        </div>
      </div>
      <dl className="readouts">
        <div>
          <dt>Ridge at this λ</dt>
          <dd>
            b = ({fixed(coef[0])}, {fixed(coef[1])}) against least squares ({fixed(ols[0])},{" "}
            {fixed(ols[1])}), from (X′X/n + λI) b = X′y/n
          </dd>
        </div>
        <div>
          <dt>Shrinkage of each direction</dt>
          <dd>
            The shared direction keeps {fixed(large / (large + lambda))} of its least squares
            value and the contrast direction {fixed(small / (small + lambda))}: the weak, collinear
            direction is shrunk hardest. Effective degrees of freedom {fixed(df, 2)} of 2.
          </dd>
        </div>
        <div>
          <dt>Choosing λ on time-ordered folds</dt>
          <dd>
            λ min = {fixed(best.lambda, 4)}; the 1-SE rule takes the largest λ within one standard
            error of it, λ = {fixed(simplest.lambda, 4)}.
          </dd>
        </div>
        <div>
          <dt>RMSE, training and later window</dt>
          <dd>
            Ridge {fixed(score(train, coef))} and {fixed(score(later, coef))}; least squares{" "}
            {fixed(score(train, ols))} and {fixed(score(later, ols))}
          </dd>
        </div>
        <div>
          <dt>Spread across {RESAMPLES} resamples</dt>
          <dd>
            Least squares ±{fixed(spread("ols", 0))} and ±{fixed(spread("ols", 1))}; ridge ±
            {fixed(spread("ridge", 0))} and ±{fixed(spread("ridge", 1))}, one standard deviation
          </dd>
        </div>
      </dl>
      <p className="muted">
        Instability is the variance of a unique minimum, not a slide to infinity. The predictors
        are standardised on the training rows so the penalty treats them alike, and the intercept,
        the mean rating, is never penalised. Seeded synthetic data: {train.length} training and{" "}
        {later.length} later ratings on five levels, with true effects 0.5 and 0.5.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: ratings({ seed: 51, n: 150 }); no real ratings"
        split="The first 120 rows train; the remaining 30 are the later window"
        method="Ridge regression, solved by Cholesky"
      />
    </article>
  );
}
