import { useCallback, useMemo, useState } from "react";
import data from "../../data/movielens.json";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps } from "../lib/grid.js";
import { constantErrors, errors, shares, weightedLine } from "../lib/macro.js";
import { mulberry32, normal } from "../lib/random.js";

const REAL = shares(data.splits["0.8/0.9"].training.counts);
const UNIFORM = [0.2, 0.2, 0.2, 0.2, 0.2];
const C = steps(1, 5, 161);
const STARS = ["1★", "2★", "3★", "4★", "5★"];

function sample(mix, n, seed) {
  const rng = mulberry32(seed);
  return Array.from({ length: n }, () => {
    const u = rng();
    let level = 0;
    let running = mix[0];
    while (u > running && level < 4) running += mix[(level += 1)];
    return level + 1;
  });
}

export default function T3() {
  const [c, setC] = useState(3.59);
  const [toward, setToward] = useState(0);
  const [predictor, setPredictor] = useState("constant");
  const [balanced, setBalanced] = useState(false);

  const mix = REAL.map((p, k) => (1 - toward) * p + toward * UNIFORM[k]);
  const mean = mix.reduce((s, p, k) => s + p * (k + 1), 0);
  const constant = predictor === "mean" ? mean : c;

  const model = useMemo(() => {
    const actual = sample(mix, 6000, 11);
    const rng = mulberry32(12);
    const signal = actual.map((y) => y + 1.2 * normal(rng));
    const line = weightedLine(signal, actual, balanced);
    return errors(signal.map(line), actual);
  }, [toward, balanced]);
  const current = predictor === "model" ? model : constantErrors(constant, mix);
  const curves = useMemo(() => C.map((value) => constantErrors(value, mix)), [toward]);
  const floor = constantErrors(3, mix);

  const curveTraces = useCallback(
    (colors) => [
      ...[
        ["pooledRmse", "Pooled RMSE", colors.muted, "solid"],
        ["pooledMae", "Pooled MAE", colors.muted, "dot"],
        ["macroRmse", "RMSE^M = √MSE^M", colors.accent, "solid"],
        ["macroMae", "MAE^M", colors.accent, "dot"],
      ].map(([key, name, color, dash]) => ({
        type: "scatter",
        mode: "lines",
        name,
        x: C,
        y: curves.map((e) => e[key]),
        line: { color, dash, width: 2.5 },
      })),
      {
        type: "scatter",
        mode: "markers",
        name: "Minima: pooled at the mean, macro at 3",
        x: [mean, 3],
        y: [constantErrors(mean, mix).pooledRmse, floor.macroRmse],
        marker: { size: 11, color: colors.ink },
      },
    ],
    [curves, mean, mix, floor],
  );
  const curveLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Constant prediction c" } },
      yaxis: { title: { text: "Error" }, rangemode: "tozero" },
    }),
    [],
  );
  const largest = Math.max(...current.perLevel);

  return (
    <article className="lab">
      <h3>Technique · Data imbalance</h3>
      <p>
        Most MovieLens ratings are 3★ or 4★, so pooled error flatters a model that ignores the
        rare levels. Macro-averaged error computes the error at each rating level and averages
        the five equally. For a constant prediction the macro score depends only on the
        constant, not on how common each rating is, which gives every model a fixed floor to
        beat: 1.20 for MAE^M and √2 ≈ 1.41 for RMSE^M, both at a constant 3. The class mix below
        starts from the real training-window shares.
      </p>
      <Plot traces={curveTraces} layout={curveLayout} label="Error by constant" height={320} />
      <div className="controls">
        <label className="control">
          <span>Predictor</span>
          <select value={predictor} onChange={(event) => setPredictor(event.target.value)}>
            <option value="constant">a constant c</option>
            <option value="mean">the mean rating</option>
            <option value="model">a fitted model</option>
          </select>
        </label>
        {predictor === "constant" && (
          <Slider label="Constant c" value={c} min={1} max={5} step={0.01} onChange={setC} />
        )}
        <Slider
          label="Class mix, from the real shares toward uniform"
          value={toward}
          min={0}
          max={1}
          step={0.05}
          onChange={setToward}
        />
        {predictor === "model" && (
          <label className="control check">
            <input
              type="checkbox"
              checked={balanced}
              onChange={(event) => setBalanced(event.target.checked)}
            />
            <span>Train with sample weights 1 / n_k</span>
          </label>
        )}
      </div>
      <h4>Error at each rating level</h4>
      <div className="bars">
        {current.perLevel.map((value, k) => (
          <div className="bar-row" key={STARS[k]}>
            <span>
              {STARS[k]} · {fixed(mix[k] * 100, 1)}% of ratings
            </span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(value / largest) * 100}%` }} />
            </div>
            <strong>{fixed(value, 2)}</strong>
          </div>
        ))}
      </div>
      <dl className="readouts">
        <div>
          <dt>Pooled</dt>
          <dd>
            RMSE {fixed(current.pooledRmse)}, MAE {fixed(current.pooledMae)}: these move with the
            class mix
          </dd>
        </div>
        <div>
          <dt>Macro-averaged</dt>
          <dd>
            RMSE^M = √((1/5) Σ MSE_k) = {fixed(current.macroRmse)}, MAE^M ={" "}
            {fixed(current.macroMae)}
          </dd>
        </div>
        <div>
          <dt>The constant floors every model must beat</dt>
          <dd>
            MAE^M {fixed(floor.macroMae, 2)} and RMSE^M {fixed(floor.macroRmse, 2)}, at c = 3, the
            same for any class mix
          </dd>
        </div>
      </dl>
      <p className="muted">
        Changing the evaluation metric does not change what squared-error training optimises:
        the models still minimise pooled error, and the macro metric changes which model is
        selected and how it is reported. Weighting training rows by 1 / n_k makes training itself
        attend to rare levels, an optional, declared intervention: with the fitted model, turn it
        on and macro error falls while pooled error rises. Real shares: training window of
        MovieLens 1M, cut at the 0.8 quantile of time.
      </p>
      <Provenance
        data="Rating-level shares from movielens.json, computed from the verified MovieLens 1M files (ratings.dat SHA-256 506d64ca); the fitted model uses 6000 synthetic ratings drawn from those shares (seeds 11 and 12)"
        split="Training window before the 0.8 quantile of time"
        method="Weighted least squares on one signal, optionally weighted by 1 / n_k"
      />
    </article>
  );
}
