import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps, surface } from "../lib/grid.js";
import { normalEquations } from "../lib/linalg.js";
import { rmse } from "../lib/metrics.js";
import { mulberry32, resample } from "../lib/random.js";
import { ratings } from "../lib/ratings.js";
import { fit, vif } from "../lib/regression.js";
import { mean } from "../lib/stats.js";

const W = steps(-0.2, 1.2, 41);
const RESAMPLES = 40;

// Centred user and film history: with b0 at the mean rating, SSE depends on (w1, w2) alone.
function centred(rows, ubar, fbar) {
  return rows.map((row) => [row.user - ubar, row.film - fbar]);
}

export default function M2() {
  const [rho, setRho] = useState(0.6);
  const [w1, setW1] = useState(0.2);
  const [w2, setW2] = useState(0.9);
  const [draw, setDraw] = useState(1);

  const train = useMemo(() => ratings({ seed: 31, n: 300, rho }), [rho]);
  const valid = useMemo(() => ratings({ seed: 32, n: 300, rho }), [rho]);
  const ys = useMemo(() => train.map((row) => row.rating), [train]);
  const ybar = useMemo(() => mean(ys), [ys]);
  const ubar = useMemo(() => mean(train.map((row) => row.user)), [train]);
  const fbar = useMemo(() => mean(train.map((row) => row.film)), [train]);
  const xs = useMemo(() => centred(train, ubar, fbar), [train, ubar, fbar]);
  const deviations = useMemo(() => ys.map((y) => y - ybar), [ys, ybar]);
  const { gram, moment } = useMemo(() => normalEquations(xs, deviations), [xs, deviations]);
  const syy = useMemo(() => deviations.reduce((total, d) => total + d * d, 0), [deviations]);
  const terms = useMemo(
    () => [{ value: (row) => row.user - ubar }, { value: (row) => row.film - fbar }],
    [ubar, fbar],
  );
  const ols = useMemo(() => fit(train, terms, ys), [train, terms, ys]);
  const inflation = useMemo(() => vif(train, terms)[0], [train, terms]);

  const sse = useCallback(
    (a, b) =>
      syy -
      2 * (a * moment[0] + b * moment[1]) +
      a * a * gram[0][0] +
      2 * a * b * gram[0][1] +
      b * b * gram[1][1],
    [syy, moment, gram],
  );
  const bowl = useMemo(() => surface(W, W, sse), [sse]);

  const cloud = useMemo(() => {
    const rng = mulberry32(1000 + draw);
    return Array.from({ length: RESAMPLES }, () => {
      const picked = resample(rng, train.length);
      const coef = fit(picked.map((i) => train[i]), terms, picked.map((i) => ys[i]));
      return [coef[1], coef[2]];
    });
  }, [draw, train, terms, ys]);
  const spread = (k) => {
    const values = cloud.map((pair) => pair[k]);
    const centre = mean(values);
    return Math.sqrt(mean(values.map((v) => (v - centre) ** 2)));
  };

  const predictAt = (a, b) => (row) => ybar + a * (row.user - ubar) + b * (row.film - fbar);
  const score = (rows, a, b) =>
    rmse(rows.map(predictAt(a, b)), rows.map((row) => row.rating));
  const left = xs.map(([u, f], index) => deviations[index] - w1 * u - w2 * f);
  const sums = [
    left.reduce((total, r) => total + r, 0),
    left.reduce((total, r, index) => total + r * xs[index][0], 0),
    left.reduce((total, r, index) => total + r * xs[index][1], 0),
  ];

  const traces = useCallback(
    (colors) => [
      {
        type: "surface",
        x: W,
        y: W,
        z: bowl,
        colorscale: "Viridis",
        opacity: 0.7,
        showscale: false,
        contours: { z: { show: true, usecolormap: true, project: { z: true } } },
        name: "SSE",
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: `${RESAMPLES} resampled fits`,
        x: cloud.map((pair) => pair[0]),
        y: cloud.map((pair) => pair[1]),
        z: cloud.map(() => 0),
        marker: { size: 3, color: colors.muted },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Your (w1, w2)",
        x: [w1],
        y: [w2],
        z: [sse(w1, w2)],
        marker: { size: 6, color: colors.accent },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Least squares",
        x: [ols[1]],
        y: [ols[2]],
        z: [sse(ols[1], ols[2])],
        marker: { size: 6, color: colors.ink, symbol: "diamond" },
      },
    ],
    [bowl, cloud, w1, w2, sse, ols],
  );

  const layout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "w1 (user history)" } },
        yaxis: { title: { text: "w2 (film history)" } },
        zaxis: { title: { text: "Sum of squared residuals" } },
        camera: { eye: { x: 1.5, y: -1.7, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 2 · Multi-linear regression</h3>
      <p>
        Two predictors, user and film history, both centred so the intercept is the mean rating.
        The bowl is the sum of squared residuals over the two slopes. As the predictors become
        correlated it stretches into a valley, and the slopes that fit equally well start to
        trade off: refitting on resampled data scatters them along the valley floor.
      </p>
      <Plot traces={traces} layout={layout} label="SSE bowl over the two slopes" height={480} />
      <div className="controls">
        <Slider label="w1, user" value={w1} min={-0.2} max={1.2} step={0.01} onChange={setW1} />
        <Slider label="w2, film" value={w2} min={-0.2} max={1.2} step={0.01} onChange={setW2} />
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
            onClick={() => {
              setW1(ols[1]);
              setW2(ols[2]);
            }}
          >
            Fit by least squares
          </button>
          <button type="button" className="action quiet" onClick={() => setDraw(draw + 1)}>
            Resample
          </button>
        </div>
      </div>
      <dl className="readouts">
        <div>
          <dt>Normal equations X′X w = X′y, centred</dt>
          <dd>
            [{fixed(gram[0][0], 1)} {fixed(gram[0][1], 1)}; {fixed(gram[1][0], 1)}{" "}
            {fixed(gram[1][1], 1)}] w = [{fixed(moment[0], 1)}; {fixed(moment[1], 1)}], solved by
            w = ({fixed(ols[1])}, {fixed(ols[2])}) and b0 = ȳ = {fixed(ols[0])}
          </dd>
        </div>
        <div>
          <dt>Orthogonality at your (w1, w2)</dt>
          <dd>
            Σr = {fixed(sums[0])}, Σr·x1 = {fixed(sums[1])}, Σr·x2 = {fixed(sums[2])}. The first
            is zero for any slopes because b0 = ȳ; the other two vanish only at the least squares
            fit.
          </dd>
        </div>
        <div>
          <dt>Sum of squared residuals</dt>
          <dd>
            {fixed(sse(w1, w2), 1)} at yours against {fixed(sse(ols[1], ols[2]), 1)} at the
            minimum
          </dd>
        </div>
        <div>
          <dt>RMSE, training and validation</dt>
          <dd>
            Yours {fixed(score(train, w1, w2))} and {fixed(score(valid, w1, w2))}; least squares{" "}
            {fixed(score(train, ols[1], ols[2]))} and {fixed(score(valid, ols[1], ols[2]))}
          </dd>
        </div>
        <div>
          <dt>Collinearity</dt>
          <dd>
            VIF = 1 / (1 − R²) = {fixed(inflation, 2)} for each slope. Across {RESAMPLES}{" "}
            resamples w1 varies by ±{fixed(spread(0))} and w2 by ±{fixed(spread(1))}, one standard
            deviation.
          </dd>
        </div>
      </dl>
      <p className="muted">
        Seeded synthetic data: {train.length} training and {valid.length} validation ratings on
        five levels, with true slopes 0.5 and 0.5. Raise ρ, then press Resample to watch the cloud
        stretch along the valley.
      </p>
    </article>
  );
}
