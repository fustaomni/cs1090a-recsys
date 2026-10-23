import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps, surface } from "../lib/grid.js";
import { rmse } from "../lib/metrics.js";
import { kkt, lambdaMax, lasso, moments, prepared, softThreshold } from "../lib/penalized.js";
import { mulberry32, subsample } from "../lib/random.js";
import { selectionRatings } from "../lib/ratings.js";
import { curve, logGrid, oneStandardError, rollingFolds } from "../lib/tuning.js";

const KEYS = ["user", "movie", "noise"];
const NAMES = ["user history", "movie history", "noise"];
const B = steps(-0.3, 1.0, 41);
const TRAIN = 160;
const DRAWS = 100;
const THRESHOLD = 0.6;

function scorer(rows) {
  return (indices, lambda) => {
    const picked = indices.train.map((index) => rows[index]);
    const { standard, ybar, xs, ys } = prepared(picked, KEYS);
    const { coef } = lasso(xs, ys, lambda);
    const later = indices.valid.map((index) => rows[index]);
    const guess = (row) => ybar + standard(row).reduce((s, x, j) => s + x * coef[j], 0);
    return rmse(later.map(guess), later.map((row) => row.rating));
  };
}

function describe(coef) {
  const kept = coef.map((b, j) => (b !== 0 ? NAMES[j] : null)).filter(Boolean);
  if (kept.length === 0) return "every coefficient is zero: λ is at or above λ max";
  const dropped = NAMES.filter((name) => !kept.includes(name));
  if (dropped.length === 0) return "all three predictors are kept";
  return `kept ${kept.join(" and ")}; set exactly to zero: ${dropped.join(" and ")}`;
}

export default function M5() {
  const [rho, setRho] = useState(0.8);
  const [fraction, setFraction] = useState(-0.6);
  const [shown, setShown] = useState(Infinity);

  const rows = useMemo(() => selectionRatings({ seed: 61, n: 200, rho }), [rho]);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const fitted = useMemo(() => prepared(train, KEYS), [train]);
  const top = useMemo(() => lambdaMax(fitted.xs, fitted.ys), [fitted]);
  const lambda = top * 10 ** fraction;
  const { coef, trace } = useMemo(() => lasso(fitted.xs, fitted.ys, lambda), [fitted, lambda]);
  const checks = kkt(fitted.xs, fitted.ys, coef, lambda);
  const sums = useMemo(() => moments(fitted.xs, fitted.ys), [fitted]);
  const syy = useMemo(
    () => fitted.ys.reduce((s, y) => s + y * y, 0) / fitted.ys.length,
    [fitted],
  );

  const cost = useCallback(
    (b) => {
      const quadratic = b.reduce(
        (s, bi, i) => s + bi * b.reduce((t, bj, j) => t + sums.gram[i][j] * bj, 0),
        0,
      );
      const linear = b.reduce((s, bi, i) => s + bi * sums.cross[i], 0);
      const penalty = b.reduce((s, bi) => s + Math.abs(bi), 0);
      return 0.5 * (syy - 2 * linear + quadratic) + lambda * penalty;
    },
    [sums, syy, lambda],
  );
  const bowl = useMemo(
    () => surface(B, B, (b1, b2) => cost([b1, b2, coef[2]])),
    [cost, coef],
  );
  const last = Math.min(shown, trace.length - 1);
  const walked = trace.slice(0, last + 1);

  const grid = useMemo(() => logGrid(top, top / 200, 40), [top]);
  const path = useMemo(
    () => grid.map((at) => lasso(fitted.xs, fitted.ys, at).coef),
    [grid, fitted],
  );
  const points = useMemo(() => curve(grid, rollingFolds(TRAIN, 5), scorer(train)), [grid, train]);
  const { best, simplest } = useMemo(() => oneStandardError(points), [points]);
  const frequency = useMemo(() => {
    const rng = mulberry32(77);
    const counts = KEYS.map(() => 0);
    for (let draw = 0; draw < DRAWS; draw += 1) {
      const picked = subsample(rng, train.length, Math.floor(train.length / 2));
      const half = prepared(picked.map((index) => train[index]), KEYS);
      lasso(half.xs, half.ys, lambda).coef.forEach((b, j) => {
        if (b !== 0) counts[j] += 1;
      });
    }
    return counts.map((count) => count / DRAWS);
  }, [train, lambda]);

  const zs = coef.map((b, j) => b + checks[j].gradient);
  const reach = Math.max(1.3 * Math.max(...zs.map(Math.abs)), 1.5 * lambda);
  const predict = (row) =>
    fitted.ybar + fitted.standard(row).reduce((s, x, j) => s + x * coef[j], 0);

  const surfaceTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        x: B,
        y: B,
        z: bowl,
        colorscale: "Viridis",
        opacity: 0.75,
        showscale: false,
        name: "Lasso objective",
      },
      {
        type: "scatter3d",
        mode: "lines+markers",
        name: "Coordinate descent from zero",
        x: walked.map((b) => b[0]),
        y: walked.map((b) => b[1]),
        z: walked.map((b) => cost([b[0], b[1], coef[2]])),
        line: { color: colors.accent, width: 5 },
        marker: { size: 3, color: colors.accent },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Lasso solution",
        x: [coef[0]],
        y: [coef[1]],
        z: [cost(coef)],
        marker: { size: 7, color: colors.ink, symbol: "diamond" },
      },
    ],
    [bowl, walked, cost, coef],
  );
  const surfaceLayout = useMemo(
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

  const thresholdTraces = useCallback(
    (colors) => {
      const zAxis = steps(-reach, reach, 81);
      return [
        {
          type: "scatter",
          mode: "lines",
          name: "S(z, λ)",
          x: zAxis,
          y: zAxis.map((z) => softThreshold(z, lambda)),
          line: { color: colors.ink, width: 2.5 },
        },
        {
          type: "scatter",
          mode: "markers+text",
          name: "Each predictor's z",
          x: zs,
          y: zs.map((z) => softThreshold(z, lambda)),
          text: NAMES,
          textposition: "top center",
          marker: { size: 10, color: colors.accent },
        },
        ...[-lambda, lambda].map((edge) => ({
          type: "scatter",
          mode: "lines",
          showlegend: false,
          x: [edge, edge],
          y: [-reach, reach],
          line: { color: colors.muted, dash: "dot" },
        })),
      ];
    },
    [reach, lambda, zs],
  );
  const pathTraces = useCallback(
    (colors) => [
      ...KEYS.map((key, k) => ({
        type: "scatter",
        mode: "lines",
        name: NAMES[k],
        x: grid,
        y: path.map((b) => b[k]),
        line: { color: [colors.accent, colors.ink, colors.muted][k], width: 2.5 },
      })),
      {
        type: "scatter",
        mode: "lines",
        name: "This λ",
        x: [lambda, lambda],
        y: [Math.min(0, ...path[path.length - 1]), Math.max(...path[path.length - 1])],
        line: { color: colors.muted, dash: "dot" },
      },
    ],
    [grid, path, lambda],
  );
  const thresholdLayout = useMemo(
    () => ({
      xaxis: { title: { text: "z = b + x′r / n" }, zeroline: true },
      yaxis: { title: { text: "New coefficient" } },
    }),
    [],
  );
  const pathLayout = useMemo(
    () => ({
      xaxis: { type: "log", title: { text: "λ (log scale); λ max at the right" } },
      yaxis: { title: { text: "Coefficient" } },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 5 · Lasso regression</h3>
      <p>
        Lasso adds λ‖b‖₁, which puts creases in the objective along each axis. It has no closed
        form: coordinate descent updates one coefficient at a time by soft-thresholding, and a
        coefficient whose z lands inside ±λ is set exactly to zero. With correlated predictors
        the choice between them is fragile, so selection is judged over many half-samples.
      </p>
      <p className="lab-state">
        At this λ: <strong>{describe(coef)}</strong>.
      </p>
      <Plot traces={surfaceTraces} layout={surfaceLayout} label="Lasso objective" height={460} />
      <div className="lab-grid">
        <Plot traces={thresholdTraces} layout={thresholdLayout} label="Soft-threshold" />
        <Plot traces={pathTraces} layout={pathLayout} label="Lasso coefficient path" />
      </div>
      <div className="controls">
        <Slider
          label="λ"
          value={fraction}
          min={-2.3}
          max={0.1}
          step={0.02}
          onChange={(value) => {
            setFraction(value);
            setShown(Infinity);
          }}
          format={(value) => `${fixed(top * 10 ** value, 4)} (λ max ${fixed(top, 4)})`}
        />
        <Slider
          label="Correlation of user and movie history ρ"
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
            onClick={() => setShown(Math.min(last + 1, trace.length - 1))}
          >
            Step coordinate descent
          </button>
          <button type="button" className="action quiet" onClick={() => setShown(0)}>
            Replay from zero
          </button>
          <button
            type="button"
            className="action quiet"
            onClick={() => {
              setFraction(Math.log10(simplest.lambda / top));
              setShown(Infinity);
            }}
          >
            Use the 1-SE λ
          </button>
        </div>
      </div>
      <dl className="readouts">
        <div>
          <dt>Lasso solution</dt>
          <dd>
            {coef.map((b, j) => `${NAMES[j]} ${fixed(b)}`).join(", ")}. The path drawn shows
            coordinate step {last} of {trace.length - 1}.
          </dd>
        </div>
        <div>
          <dt>KKT check, |x′r| / n against λ = {fixed(lambda, 4)}</dt>
          <dd>
            {checks
              .map(
                (check, j) =>
                  `${NAMES[j]} ${fixed(Math.abs(check.gradient), 4)} ${check.holds ? "✓" : "✗"}`,
              )
              .join(", ")}
          </dd>
        </div>
        <div>
          <dt>Choosing λ on time-ordered folds</dt>
          <dd>
            λ min = {fixed(best.lambda, 4)}, λ 1-SE = {fixed(simplest.lambda, 4)}. Later-window
            RMSE at this λ {fixed(rmse(later.map(predict), later.map((row) => row.rating)))}.
          </dd>
        </div>
      </dl>
      <h4>Stability selection: {DRAWS} half-samples drawn without replacement, at this λ</h4>
      <div className="bars">
        {frequency.map((share, j) => (
          <div className="bar-row" key={KEYS[j]}>
            <span>{NAMES[j]}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${share * 100}%` }} />
              <div className="bar-mark" style={{ left: `${THRESHOLD * 100}%` }} />
            </div>
            <strong>{fixed(share * 100, 0)}%</strong>
          </div>
        ))}
      </div>
      <p className="muted">
        A predictor is stable if it is selected in at least {THRESHOLD * 100}% of half-samples,
        the line on each bar. Raise ρ and the two correlated histories trade places from sample
        to sample. Ridge never sets a coefficient to zero; lasso does, and that is both its use
        and its fragility. Seeded synthetic data: {train.length} training and {later.length}{" "}
        later ratings on five levels; the noise predictor has no effect.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: selectionRatings({ seed: 61, n: 200 }); no real ratings"
        split="The first 160 rows train; the remaining 40 are the later window"
        method="Lasso, by cyclic coordinate descent with soft-thresholding"
      />
    </article>
  );
}
