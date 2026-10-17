import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { earlyStopping, gradientBoost } from "../lib/boosting.js";
import { blockSurface } from "../lib/ensemble.js";
import { fixed } from "../lib/format.js";
import { outOfRange } from "../lib/metrics.js";
import { forestRatings } from "../lib/ratings.js";

const FEATURES = ["user", "movie"];
const STAGES = 150;
const RANGE = [-2.5, 2.5];
const WORKED = 8;

// Every row's prediction after each stage, accumulated once so the curves are cheap.
function staged(fit, rows) {
  return rows.map((row) => {
    const path = [fit.start];
    for (const step of fit.steps) {
      path.push(path[path.length - 1] + fit.learningRate * step.step(row));
    }
    return path;
  });
}

function rmseAt(paths, rows, stage) {
  const total = rows.reduce((s, row, i) => s + (paths[i][stage] - row.rating) ** 2, 0);
  return Math.sqrt(total / rows.length);
}

export default function M11() {
  const [stage, setStage] = useState(20);
  const [rate, setRate] = useState(0.1);
  const [splits, setSplits] = useState(4);
  const [subsample, setSubsample] = useState(1);
  const [loss, setLoss] = useState("squared");
  const [patience, setPatience] = useState(15);
  const [worked, setWorked] = useState(0);

  const rows = useMemo(() => forestRatings({ seed: 141, n: 300 }), []);
  const train = useMemo(() => rows.slice(0, 200), [rows]);
  const valid = useMemo(() => rows.slice(200, 250), [rows]);
  const test = useMemo(() => rows.slice(250), [rows]);
  const fit = useMemo(
    () =>
      gradientBoost(train, FEATURES, {
        stages: STAGES,
        learningRate: rate,
        splits,
        subsample,
        loss,
        seed: 3,
      }),
    [train, rate, splits, subsample, loss],
  );
  const paths = useMemo(
    () => ({ train: staged(fit, train), valid: staged(fit, valid), test: staged(fit, test) }),
    [fit, train, valid, test],
  );
  const curves = useMemo(() => {
    const at = (name, set) =>
      Array.from({ length: STAGES + 1 }, (_, m) => rmseAt(paths[name], set, m));
    return { train: at("train", train), valid: at("valid", valid) };
  }, [paths, train, valid]);
  const stop = earlyStopping(curves.valid, patience);
  const finalTest = rmseAt(paths.test, test, stop.best);
  const heldOut = [...valid, ...test].map((row) => fit.predict(row, stop.best));

  const current = Math.max(1, stage);
  const latest = fit.steps[current - 1];
  const predict = useCallback((row) => fit.predict(row, current), [fit, current]);
  const surface = useMemo(
    () => blockSurface(predict, "user", "movie", RANGE, RANGE, 40, {}),
    [predict],
  );
  const residualSurface = useMemo(
    () => blockSurface(latest.step, "user", "movie", RANGE, RANGE, 40, {}),
    [latest],
  );
  const row = train[worked];
  const path = paths.train[worked];
  const early = Array.from({ length: Math.min(WORKED, current) }, (_, k) => k + 1);
  const steps = [...new Set([...early, current])];

  const surfaceTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        ...surface,
        colorscale: "Viridis",
        opacity: 0.9,
        showscale: false,
        name: `F after ${current} stages`,
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Training ratings",
        x: train.map((r) => r.user),
        y: train.map((r) => r.movie),
        z: train.map((r) => r.rating),
        marker: { size: 2.5, color: colors.muted, opacity: 0.6 },
      },
    ],
    [surface, current, train],
  );
  const residualTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        ...residualSurface,
        colorscale: "RdBu",
        opacity: 0.85,
        showscale: false,
        name: `Tree ${current}, fitted to the residuals`,
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: `Residuals before stage ${current}`,
        x: train.map((r) => r.user),
        y: train.map((r) => r.movie),
        z: latest.residuals,
        marker: { size: 2.5, color: colors.accent, opacity: 0.8 },
      },
    ],
    [residualSurface, current, train, latest],
  );
  const curveTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines",
        name: "Training RMSE",
        x: curves.train.map((_, m) => m),
        y: curves.train,
        line: { color: colors.muted },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Validation RMSE (later window)",
        x: curves.valid.map((_, m) => m),
        y: curves.valid,
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "markers",
        name: "Best stage, kept",
        x: [stop.best],
        y: [curves.valid[stop.best]],
        marker: { size: 12, color: colors.accent },
      },
      {
        type: "scatter",
        mode: "markers",
        name: "Stopped here",
        x: [stop.stoppedAt],
        y: [curves.valid[stop.stoppedAt]],
        marker: { size: 10, color: colors.accent, symbol: "x" },
      },
    ],
    [curves, stop],
  );
  const scene = (z) => ({
    scene: {
      xaxis: { title: { text: "User history" } },
      yaxis: { title: { text: "Movie history" } },
      zaxis: { title: { text: z } },
      camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
    },
    margin: { l: 0, r: 0, t: 0, b: 0 },
  });
  const surfaceLayout = useMemo(() => scene("Prediction F"), []);
  const residualLayout = useMemo(() => scene("Residual"), []);
  const curveLayout = useMemo(
    () => ({ xaxis: { title: { text: "Stage" } }, yaxis: { title: { text: "RMSE" } } }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 11 · Gradient boosting</h3>
      <p>
        Gradient boosting starts from the mean rating and adds trees one at a time. Each tree is
        fitted to the negative gradient of the loss at the current prediction, which for squared
        error is simply the residual y − F, and only a fraction ν of it is added. On the left is
        the prediction so far; on the right, the residuals the next tree is fitted to and that
        tree's own surface.
      </p>
      <div className="lab-grid">
        <Plot traces={surfaceTraces} layout={surfaceLayout} label="Prediction after m stages" />
        <Plot traces={residualTraces} layout={residualLayout} label="Residuals and next tree" />
      </div>
      <div className="controls">
        <Slider
          label="Stage m"
          value={stage}
          min={1}
          max={STAGES}
          step={1}
          onChange={setStage}
          format={String}
        />
        <Slider
          label="Learning rate ν"
          value={rate}
          min={0.02}
          max={1}
          step={0.02}
          onChange={setRate}
        />
        <Slider
          label="Splits per tree"
          value={splits}
          min={1}
          max={8}
          step={1}
          onChange={setSplits}
          format={String}
        />
        <Slider
          label="Subsample per stage"
          value={subsample}
          min={0.5}
          max={1}
          step={0.05}
          onChange={setSubsample}
        />
        <Slider
          label="Early-stopping patience"
          value={patience}
          min={5}
          max={40}
          step={1}
          onChange={setPatience}
          format={String}
        />
        <label className="control">
          <span>Loss</span>
          <select value={loss} onChange={(event) => setLoss(event.target.value)}>
            <option value="squared">squared: fit the residual</option>
            <option value="absolute">absolute: fit its sign</option>
          </select>
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Early stopping on the validation window</dt>
          <dd>
            Best at stage {stop.best} (validation RMSE {fixed(curves.valid[stop.best])}); no
            improvement for {patience} stages after it, so boosting stopped at stage{" "}
            {stop.stoppedAt} and rolled back to {stop.best}.
          </dd>
        </div>
        <div>
          <dt>Final score on the test window</dt>
          <dd>
            {fixed(finalTest)} at the kept stage, measured once, after the stage was chosen on
            validation
          </dd>
        </div>
        <div>
          <dt>Predictions outside [1, 5]</dt>
          <dd>
            {outOfRange(heldOut)} of {heldOut.length} held-out predictions: a sum of shrunken trees
            can step past the scale
          </dd>
        </div>
      </dl>
      <Plot traces={curveTraces} layout={curveLayout} label="RMSE against stage" height={300} />
      <h4>One training row, worked through the stages</h4>
      <div className="controls">
        <Slider
          label="Training row"
          value={worked}
          min={0}
          max={train.length - 1}
          step={1}
          onChange={setWorked}
          format={(value) => `#${value + 1}, rated ${train[value].rating}`}
        />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Stage m</th>
              <th scope="col">Before: F</th>
              <th scope="col">Residual y − F</th>
              <th scope="col">Tree's value h(x)</th>
              <th scope="col">After: F + ν·h(x)</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((m) => (
              <tr key={m}>
                <th scope="row">{m}</th>
                <td>{fixed(path[m - 1])}</td>
                <td>{fixed(row.rating - path[m - 1])}</td>
                <td>{fixed(fit.steps[m - 1].step(row))}</td>
                <td>{fixed(path[m])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        The stage is chosen by the error on the later validation window, never on a random slice
        of the training rows, and the test window is scored once at the end. Seeded synthetic
        data: {train.length} training, {valid.length} validation and {test.length} test ratings
        on five levels.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: forestRatings({ seed: 141, n: 300 }); no real ratings"
        split="200 training rows, then 50 validation and 50 test rows in time order"
        features="user, movie"
        method="Gradient boosting with shrinkage, stopped early on the validation window, seed 3"
      />
    </article>
  );
}
