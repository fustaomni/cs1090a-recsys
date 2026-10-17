import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps, surface } from "../lib/grid.js";
import { percentile, replicates } from "../lib/inference.js";
import { rmse } from "../lib/metrics.js";
import { stackingRatings } from "../lib/ratings.js";
import { ambiguity, correlation, metaFit, metaObjective } from "../lib/stacking.js";

const W = steps(-0.8, 1.6, 41);
const BLOCK = 100;
const METHODS = {
  ols: "Ordinary least squares",
  nnls: "Non-negative least squares",
  ridge: "Non-negative ridge",
};

export default function M12() {
  const [method, setMethod] = useState("ridge");
  const [exponent, setExponent] = useState(-1);
  const [sumToOne, setSumToOne] = useState(false);
  const [rho, setRho] = useState(0.8);
  const lambda = 10 ** exponent;
  const penalty = method === "ridge" ? lambda : 0;

  const rows = useMemo(() => stackingRatings({ seed: 161, n: 500, correlation: rho }), [rho]);
  const meta = useMemo(() => rows.slice(BLOCK, 4 * BLOCK), [rows]);
  const test = useMemo(() => rows.slice(4 * BLOCK), [rows]);
  const fit = useMemo(
    () =>
      metaFit(
        meta.map((r) => r.base),
        meta.map((r) => r.rating),
        { method, lambda, sumToOne },
      ),
    [meta, method, lambda, sumToOne],
  );
  const bowl = useMemo(
    () => surface(W, W, (a, b) => metaObjective(fit.stats, [a, b], penalty)),
    [fit, penalty],
  );
  const floor = Math.min(...bowl.flat());

  const errors = (j) => meta.map((r) => r.base[j] - r.rating);
  const predictionCorrelation = correlation(
    meta.map((r) => r.base[0]),
    meta.map((r) => r.base[1]),
  );
  const residualCorrelation = correlation(errors(0), errors(1));
  const usable = fit.w.every((v) => v >= 0) && fit.w.some((v) => v > 0);
  const share = usable ? fit.w.map((v) => v / (fit.w[0] + fit.w[1])) : [0.5, 0.5];
  const decomposition = ambiguity(
    meta.map((r) => r.base),
    meta.map((r) => r.rating),
    share,
  );

  const actual = test.map((r) => r.rating);
  const singles = [0, 1].map((j) => rmse(test.map((r) => r.base[j]), actual));
  const bestSingle = singles[0] <= singles[1] ? 0 : 1;
  const comparison = useMemo(() => {
    const paired = test.map((r) => ({
      user: r.user,
      film: 0,
      rating: r.rating,
      a: r.base[bestSingle],
      b: fit.predict(r.base),
    }));
    const draws = replicates(paired, "user", 40, 1, 1000, 17).map((d) => d.difference);
    return { low: percentile(draws, 0.025), high: percentile(draws, 0.975) };
  }, [test, fit, bestSingle]);
  const ensembleRmse = rmse(test.map((r) => fit.predict(r.base)), actual);
  const gain = singles[bestSingle] - ensembleRmse;

  const traces = useCallback(
    (colors) => {
      const objective = (w) => metaObjective(fit.stats, w, penalty);
      const result = [
        {
          type: "surface",
          x: W,
          y: W,
          z: bowl,
          colorscale: "Viridis",
          opacity: 0.75,
          showscale: false,
          name: "Meta-learner objective",
        },
        {
          type: "mesh3d",
          x: [0, 1.6, 1.6, 0],
          y: [0, 0, 1.6, 1.6],
          z: [floor, floor, floor, floor],
          i: [0, 0],
          j: [1, 2],
          k: [2, 3],
          color: colors.accent,
          opacity: 0.25,
          name: "Feasible: both weights ≥ 0",
          showlegend: true,
          hoverinfo: "skip",
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: "Unconstrained minimum",
          x: [fit.unconstrained[0]],
          y: [fit.unconstrained[1]],
          z: [objective(fit.unconstrained)],
          marker: { size: 6, color: colors.ink, symbol: "diamond" },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: `${METHODS[method]}${sumToOne ? ", weights sum to one" : ""}`,
          x: [fit.w[0]],
          y: [fit.w[1]],
          z: [objective(fit.w)],
          marker: { size: 8, color: colors.accent },
        },
      ];
      if (sumToOne) {
        const line = steps(-0.6, 1.6, 30);
        result.push({
          type: "scatter3d",
          mode: "lines",
          name: "w₁ + w₂ = 1",
          x: line,
          y: line.map((a) => 1 - a),
          z: line.map((a) => objective([a, 1 - a])),
          line: { color: colors.ink, width: 4 },
        });
      }
      return result;
    },
    [bowl, floor, fit, penalty, method, sumToOne],
  );
  const layout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "w₁, base model A" } },
        yaxis: { title: { text: "w₂, base model B" } },
        zaxis: { title: { text: "Objective" } },
        camera: { eye: { x: 1.5, y: -1.7, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );
  const largest = Math.max(decomposition.member, 1e-9);

  return (
    <article className="lab">
      <h3>Model 12 · Stacking and blending</h3>
      <p>
        A meta-learner weights the base models' out-of-fold predictions. Because those
        predictions all track the same rating they are highly correlated, so least squares can
        put a negative weight on one model; a non-negativity constraint forbids that, and a
        ridge penalty pulls correlated weights toward each other. A weight lands exactly on zero
        only when the constraint binds, where the unconstrained minimum lies outside the shaded
        region.
      </p>
      <Plot traces={traces} layout={layout} label="Meta-learner objective" height={480} />
      <div className="controls">
        <label className="control">
          <span>Meta-learner</span>
          <select value={method} onChange={(event) => setMethod(event.target.value)}>
            {Object.entries(METHODS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {method === "ridge" && (
          <Slider
            label="λ"
            value={exponent}
            min={-3}
            max={0}
            step={0.05}
            onChange={setExponent}
            format={(value) => fixed(10 ** value, 3)}
          />
        )}
        <Slider
          label="Correlation of the base models' errors"
          value={rho}
          min={0}
          max={0.97}
          step={0.01}
          onChange={setRho}
        />
        <label className="control check">
          <input
            type="checkbox"
            checked={sumToOne}
            onChange={(event) => setSumToOne(event.target.checked)}
          />
          <span>Weights sum to one (otherwise an unpenalised intercept)</span>
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Weights</dt>
          <dd>
            w = ({fixed(fit.w[0])}, {fixed(fit.w[1])}), sum {fixed(fit.w[0] + fit.w[1])},
            intercept {fixed(fit.intercept)}; unconstrained ({fixed(fit.unconstrained[0])},{" "}
            {fixed(fit.unconstrained[1])})
          </dd>
        </div>
        <div>
          <dt>Constraint</dt>
          <dd>
            {fit.binding.some(Boolean)
              ? `binding: base model ${fit.binding[0] ? "A" : "B"} is set to zero, because ` +
                "its unconstrained weight was negative"
              : "not binding: both weights are free"}
          </dd>
        </div>
        <div>
          <dt>Does stacking beat the best single model?</dt>
          <dd>
            On the last block, RMSE {fixed(ensembleRmse)} against {fixed(singles[bestSingle])} for
            base model {bestSingle === 0 ? "A" : "B"}: a gain of {fixed(gain)}, with a
            user-clustered 95% interval from {fixed(comparison.low)} to {fixed(comparison.high)}
            {comparison.low > 0 ? ", which excludes zero" : ", which includes zero"}.
          </dd>
        </div>
      </dl>
      <h4>Diversity, measured on errors</h4>
      <p>
        The base models' predictions correlate at {fixed(predictionCorrelation, 2)}, which says
        little; their errors correlate at {fixed(residualCorrelation, 2)}, which is what limits
        the gain. For an average with weights ({fixed(share[0], 2)}, {fixed(share[1], 2)}),
        ensemble error is member error minus ambiguity:
      </p>
      <div className="bars">
        {[
          ["average member error", decomposition.member],
          ["ambiguity", decomposition.spread],
          ["ensemble error", decomposition.ensemble],
        ].map(([label, value]) => (
          <div className="bar-row" key={label}>
            <span>{label}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(value / largest) * 100}%` }} />
            </div>
            <strong>{fixed(value)}</strong>
          </div>
        ))}
      </div>
      <p className="muted">
        The meta-learner is trained on out-of-fold predictions from time-ordered folds, so the
        first block, which no fold validates, has none: it is left out, blocks two to four train
        the weights and the last block scores them. Seeded synthetic predictions: {meta.length}{" "}
        meta-training and {test.length} test ratings.
      </p>
    </article>
  );
}
