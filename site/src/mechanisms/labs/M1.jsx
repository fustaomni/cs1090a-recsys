import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { steps, surface } from "../lib/grid.js";
import { clip, outOfRange, rmse } from "../lib/metrics.js";
import { TRUTH, ratings } from "../lib/ratings.js";
import { simpleFit, sse, sums } from "../lib/stats.js";

const B0 = steps(2, 5, 41);
const B1 = steps(-1, 2, 41);
const JITTER = 0.12;

export default function M1() {
  const [rho, setRho] = useState(0.5);
  const [b0, setB0] = useState(3.0);
  const [b1, setB1] = useState(0.0);

  const rows = useMemo(() => ratings({ seed: 11, n: 300, rho }), [rho]);
  const xs = useMemo(() => rows.map((row) => row.user), [rows]);
  const ys = useMemo(() => rows.map((row) => row.rating), [rows]);
  const fit = useMemo(() => simpleFit(xs, ys), [xs, ys]);
  const totals = useMemo(() => sums(xs, ys), [xs, ys]);
  const bowl = useMemo(() => surface(B0, B1, (a, b) => sse(totals, a, b)), [totals]);

  const predictions = xs.map((x) => b0 + b1 * (x - fit.xbar));
  const outside = outOfRange(predictions);
  const fitPredictions = xs.map((x) => fit.b0 + fit.b1 * (x - fit.xbar));
  const expected = TRUTH.user + TRUTH.movie * rho;

  const scatter = useCallback(
    (colors) => {
      const lo = Math.min(...xs);
      const hi = Math.max(...xs);
      const line = (a, b) => [a + b * (lo - fit.xbar), a + b * (hi - fit.xbar)];
      return [
        {
          type: "scatter",
          mode: "markers",
          name: "Ratings (jittered for display)",
          x: xs,
          y: ys.map((y, index) => y + JITTER * Math.sin(index * 12.9898)),
          marker: { size: 5, color: colors.muted, opacity: 0.55 },
        },
        {
          type: "scatter",
          mode: "lines",
          name: "Your line",
          x: [lo, hi],
          y: line(b0, b1),
          line: { color: colors.accent, width: 3 },
        },
        {
          type: "scatter",
          mode: "lines",
          name: "Least squares",
          x: [lo, hi],
          y: line(fit.b0, fit.b1),
          line: { color: colors.ink, width: 2, dash: "dash" },
        },
      ];
    },
    [xs, ys, fit, b0, b1],
  );

  const scatterLayout = useMemo(
    () => ({
      xaxis: { title: { text: "User history (standardised)" } },
      yaxis: { title: { text: "Rating" }, range: [0, 6], dtick: 1 },
      shapes: [0.5, 5.5].map((y) => ({
        type: "line",
        xref: "paper",
        x0: 0,
        x1: 1,
        y0: y,
        y1: y,
        line: { dash: "dot", width: 1, color: "rgba(127,127,127,0.6)" },
      })),
    }),
    [],
  );

  const bowlTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        x: B0,
        y: B1,
        z: bowl,
        colorscale: "Viridis",
        opacity: 0.85,
        showscale: false,
        contours: { z: { show: true, usecolormap: true, project: { z: true } } },
        name: "SSE",
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Your (b0, b1)",
        x: [b0],
        y: [b1],
        z: [sse(totals, b0, b1)],
        marker: { size: 6, color: colors.accent },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Least squares minimum",
        x: [fit.b0],
        y: [fit.b1],
        z: [sse(totals, fit.b0, fit.b1)],
        marker: { size: 6, color: colors.ink, symbol: "diamond" },
      },
    ],
    [bowl, b0, b1, fit, totals],
  );

  const bowlLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "b0 (intercept)" } },
        yaxis: { title: { text: "b1 (slope)" } },
        zaxis: { title: { text: "Sum of squared residuals" } },
        camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 1 · Simple linear regression</h3>
      <p>
        One predictor, the user's history, fits a line to ratings that only take the values 1 to
        5. Move the line yourself, or let least squares choose it: the choice is the lowest point
        of the bowl on the right, where the sum of squared residuals is smallest.
      </p>
      <div className="lab-grid">
        <Plot traces={scatter} layout={scatterLayout} label="Ratings against user history" />
        <Plot traces={bowlTraces} layout={bowlLayout} label="Sum of squared residuals bowl" />
      </div>
      <div className="controls">
        <Slider label="Intercept b0" value={b0} min={2} max={5} step={0.01} onChange={setB0} />
        <Slider label="Slope b1" value={b1} min={-1} max={2} step={0.01} onChange={setB1} />
        <Slider
          label="Correlation of user and movie history ρ"
          value={rho}
          min={0}
          max={0.9}
          step={0.05}
          onChange={setRho}
        />
        <button
          type="button"
          className="action"
          onClick={() => {
            setB0(fit.b0);
            setB1(fit.b1);
          }}
        >
          Fit by least squares
        </button>
      </div>
      <dl className="readouts">
        <div>
          <dt>Least squares</dt>
          <dd>
            b1 = cov(x, y) / var(x) = {fit.b1.toFixed(3)}; b0 = ȳ = {fit.b0.toFixed(3)}, since x
            is centred
          </dd>
        </div>
        <div>
          <dt>Your line</dt>
          <dd>
            SSE {sse(totals, b0, b1).toFixed(1)} against the minimum{" "}
            {sse(totals, fit.b0, fit.b1).toFixed(1)}
          </dd>
        </div>
        <div>
          <dt>RMSE, unclipped and clipped to [1, 5]</dt>
          <dd>
            {rmse(predictions, ys).toFixed(3)} and {rmse(predictions.map(clip), ys).toFixed(3)};
            least squares {rmse(fitPredictions, ys).toFixed(3)}
          </dd>
        </div>
        <div>
          <dt>Predictions outside [1, 5]</dt>
          <dd>
            {outside} of {predictions.length}, counted and never clipped before the residuals
          </dd>
        </div>
        <div>
          <dt>Omitted-variable bias</dt>
          <dd>
            The true user effect is {TRUTH.user}; movie history, left out, has effect{" "}
            {TRUTH.movie}. The fitted slope {fit.b1.toFixed(3)} absorbs about ρ × {TRUTH.movie}:
            before rounding to levels it would be {expected.toFixed(3)}.
          </dd>
        </div>
      </dl>
      <p className="muted">
        Seeded synthetic data: {rows.length} ratings, ρ = {rho.toFixed(2)}. Rounding to five
        levels flattens the slope a little, which is why the fit sits near, not on, the value
        before rounding.
      </p>
    </article>
  );
}
